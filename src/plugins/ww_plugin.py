"""WW Plugin System — base interface and scanner."""
import importlib
import inspect
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
import enum
from pydantic import BaseModel


class PluginCapability(str, enum.Enum):
    """Capabilities a plugin can request. Used for permission checking."""
    NONE = "none"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    SHELL_EXEC = "shell_exec"
    NETWORK_ACCESS = "network_access"
    MEMORY_ACCESS = "memory_access"
    TOOL_REGISTRATION = "tool_registration"
    AGENT_DELEGATION = "agent_delegation"


class PluginSpec(BaseModel):
    """Schema describing a plugin's metadata and capabilities."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    requires: List[str] = []
    capabilities: List[PluginCapability] = [PluginCapability.TOOL_REGISTRATION]
    permissions: Dict[str, Any] = {}


class WWPlugin:
    """Base class for all WW plugins.
    
    Subclass this and implement the register_tools() method to add
    custom tools to the bridge's ToolRegistry.
    
    Capabilities:
        Override `capabilities` to declare what your plugin needs.
        The system will check capabilities before granting access.
    """
    
    @property
    def capabilities(self) -> List[PluginCapability]:
        """Declare what capabilities this plugin requires."""
        return [PluginCapability.TOOL_REGISTRATION]
    
    def __init__(self):
        self.spec: PluginSpec = PluginSpec(name=self.__class__.__name__)
        self._initialized = False
    
    async def init(self) -> None:
        """Called once when the plugin is loaded. Override for setup."""
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Called when the bridge shuts down. Override for cleanup."""
        self._initialized = False
    
    def register_tools(self, registry) -> None:
        """Override this to register custom tools with the ToolRegistry.
        
        Example:
            registry.register("my_tool", my_func, "Description", MyArgs)
        """
        pass


# ── Example Plugin ────────────────────────────────────────────────

class ExampleNotebookPlugin(WWPlugin):
    """Example plugin that registers a simple 'notebook' tool.
    
    Provides a lightweight key-value scratchpad that agents can use
    to store and retrieve notes during a session.
    """

    def __init__(self):
        super().__init__()
        self.spec = PluginSpec(
            name="ExampleNotebookPlugin",
            version="0.1.0",
            description="Simple key-value notebook for agent scratchpad",
        )
        self._notes: dict = {}

    def register_tools(self, registry) -> None:
        """Register notebook_read and notebook_write tools."""
        from pydantic import BaseModel, Field

        class NotebookReadArgs(BaseModel):
            key: str = Field(..., description="The notebook key to read.")

        class NotebookWriteArgs(BaseModel):
            key: str = Field(..., description="The notebook key to write.")
            value: str = Field(..., description="The value to store.")

        async def notebook_read(key: str) -> str:
            val = self._notes.get(key)
            if val is None:
                return f"NOTEBOOK: No entry found for key '{key}'."
            return f"NOTEBOOK[{key}]: {val}"

        async def notebook_write(key: str, value: str) -> str:
            self._notes[key] = value
            return f"NOTEBOOK: Stored {len(value)} bytes under '{key}'."

        registry.register(
            "notebook_read", notebook_read,
            "Read a key from the agent notebook scratchpad.",
            NotebookReadArgs, tags=["notebook", "memory"],
        )
        registry.register(
            "notebook_write", notebook_write,
            "Write a key-value pair to the agent notebook scratchpad.",
            NotebookWriteArgs, tags=["notebook", "memory"],
        )
    
    def get_tool_definitions(self) -> str:
        """Return a string describing this plugin's tools for LLM context."""
        return ""


class PluginScanner:
    """Scans the plugins/ directory and loads all valid plugins."""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, WWPlugin] = {}
    
    def discover(self) -> List[str]:
        """Scan for plugin modules and return their names.
        
        Supports both single-file plugins (*.py) and package plugins
        (subdirectories with __init__.py)."""
        if not self.plugin_dir.exists():
            return []
        plugin_names = []
        
        # Single-file plugins
        for f in sorted(self.plugin_dir.glob("*.py")):
            if f.name.startswith("_") or f.name == "__init__.py":
                continue
            plugin_names.append(f.stem)
        
        # Package plugins (subdirectories with __init__.py)
        for d in sorted(self.plugin_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                init_file = d / "__init__.py"
                if init_file.exists():
                    plugin_names.append(d.name)
        
        return plugin_names
    
    async def load_all(self, registry) -> List[str]:
        """Load all discovered plugins and call their register_tools()."""
        loaded = []
        
        # Helper to inject 'plugin' tag into registry calls
        class TaggedRegistry:
            def __init__(self, inner, plugin_name):
                self.inner = inner
                self.plugin_name = plugin_name
            
            def register(self, name, func, description, schema=None, dependencies=None, tags=None):
                tags = tags or []
                if "plugin" not in tags: tags.append("plugin")
                if f"plugin:{self.plugin_name}" not in tags: tags.append(f"plugin:{self.plugin_name}")
                self.inner.register(name, func, description, schema, dependencies, tags)

        for name in self.discover():
            try:
                # Force reload module if it's already in sys.modules
                full_module_name = f"plugins.{name}"
                if full_module_name in sys.modules:
                    importlib.reload(sys.modules[full_module_name])

                # Check if it's a package plugin (directory with __init__.py)
                pkg_dir = self.plugin_dir / name
                if pkg_dir.is_dir():
                    spec = importlib.util.spec_from_file_location(
                        full_module_name,
                        pkg_dir / "__init__.py"
                    )
                else:
                    spec = importlib.util.spec_from_file_location(
                        full_module_name,
                        self.plugin_dir / f"{name}.py"
                    )
                
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, WWPlugin) and attr is not WWPlugin:
                            plugin_instance = attr()
                            await plugin_instance.init()
                            
                            # Use the tagged registry wrapper
                            plugin_instance.register_tools(TaggedRegistry(registry, name))
                            
                            self.plugins[name] = plugin_instance
                            loaded.append(name)
                            break
            except Exception as e:
                print(f"  [plugin] Failed to load '{name}': {e}")
        return loaded
    
    async def reload_all(self, registry) -> List[str]:
        """Shut down, clear tools, and reload all plugins."""
        await self.shutdown_all()
        registry.clear_by_tag("plugin")
        return await self.load_all(registry)
    
    async def shutdown_all(self):
        """Shut down all loaded plugins."""
        for name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
            except Exception:
                pass
        self.plugins.clear()
