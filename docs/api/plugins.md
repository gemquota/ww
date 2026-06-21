# Plugin System

WW supports runtime extensibility via plugins.

## Architecture

- **Base class**: `WWPlugin` in `src/plugins/ww_plugin.py`
- **Scanner**: `PluginScanner` discovers and loads plugins

## Creating a Plugin

```python
from src.plugins.ww_plugin import WWPlugin, PluginSpec
from pydantic import BaseModel, Field

class MyPlugin(WWPlugin):
    def __init__(self):
        super().__init__()
        self.spec = PluginSpec(name="MyPlugin", version="0.1.0")

    def register_tools(self, registry):
        class MyArgs(BaseModel):
            query: str = Field(..., description="Search query")
        async def my_tool(query: str) -> str:
            return f"Result for: {query}"
        registry.register("my_tool", my_tool, "Description", MyArgs)
```

## Package Plugins
```
plugins/
  my_plugin/
    __init__.py
    helpers.py
```
