"""
BridgeContext — centralized state container for the WW Bridge.

Replaces module-level mutable singletons with a single dataclass
that is explicitly constructed and passed to subsystems.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict

from src.config import Settings
from src.context_manager import ConversationHistory, TokenCounter
from src.permissions import PermissionManager
from src.checkpoint import CheckpointManager
from src.diff_engine import DiffEngine
from src.telemetry import TelemetryManager
from src.core.memory import MemoryManager
from src.core.healing import AutoHealer
from src.bridge.causal_graph import CausalGraph
from src.tools.registry import ToolRegistry
from src.tools.system_tools import (
    read_file, list_dir, write_file, shell_exec, git_tool,
    doc_search, request_clarification, code_search, file_patch, url_fetch,
    ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs,
    GitArgs, DocSearchArgs, ClarificationArgs,
    CodeSearchArgs, FilePatchArgs, UrlFetchArgs
)
from src.permissions import ApprovalPolicy
from src.utils.web_client import WebGeminiClient


@dataclass
class BridgeContext:
    """Consolidated state and service instances for the bridge runtime."""

    # Configuration
    settings: Settings
    workspace_root: Path
    secure_1psid: str = ""
    secure_1psidts: str = ""
    api_key: str = ""

    # Core systems (initialized at startup)
    conversation: Optional[ConversationHistory] = None
    token_counter: Optional[TokenCounter] = None
    permission_mgr: Optional[PermissionManager] = None
    checkpoint_mgr: Optional[CheckpointManager] = None
    diff_engine: Optional[DiffEngine] = None
    telemetry: Optional[TelemetryManager] = None
    memory: Optional[MemoryManager] = None
    causal_graph: Optional[CausalGraph] = None
    decision_tracer: Optional[Any] = None
    healer: Optional[AutoHealer] = None
    web_client: Optional[WebGeminiClient] = None

    # Tool system
    tool_registry: Optional[ToolRegistry] = None
    tool_defs: list = field(default_factory=list)

    # Plugin system
    plugin_scanner: Optional[Any] = None  # PluginScanner type

    # Runtime state
    verbose_mode: bool = False
    bridge_status: str = "Idle"
    agent_sessions: Dict[str, Any] = field(default_factory=dict)
    chat_context: dict = field(default_factory=dict)
    chat: Any = None  # Gemini chat object
    shutdown_requested: bool = False

    @classmethod
    def create_default(cls) -> "BridgeContext":
        """Factory method — creates a fully-initialized BridgeContext from settings."""
        from src.config import get_settings
        import os

        settings = get_settings()
        workspace_root = settings.resolve_workspace()
        credential_sid = settings.gemini.credentials.secure_1psid or os.getenv("SECURE_1PSID", "")
        credential_sidts = settings.gemini.credentials.secure_1psidts or os.getenv("SECURE_1PSIDTS", "")
        api_key = os.getenv("GEMINI_API_KEY", "")

        ctx = cls(
            settings=settings,
            workspace_root=workspace_root,
            secure_1psid=credential_sid,
            secure_1psidts=credential_sidts,
            api_key=api_key,
            conversation=ConversationHistory(context_window=settings.context_window),
            token_counter=TokenCounter(),
            permission_mgr=PermissionManager(
                workspace_root,
                ApprovalPolicy[
                    settings.policy.upper().replace("-", "_")
                ]
            ),
            checkpoint_mgr=CheckpointManager(workspace_root),
            diff_engine=DiffEngine(),
            telemetry=TelemetryManager(workspace_root),
            tool_registry=ToolRegistry(),
            verbose_mode=False,
            bridge_status="Idle",
        )

        # Register built-in tools
        ctx.tool_registry.register("read_file", read_file, "Read contents of a file.", ReadFileArgs, tags=["read", "research"])
        ctx.tool_registry.register("write_file", write_file, "Write contents to a file.", WriteFileArgs, tags=["write", "edit"])
        ctx.tool_registry.register("list_dir", list_dir, "List files in a directory.", ListDirArgs, tags=["read", "research"])
        ctx.tool_registry.register("shell_exec", shell_exec, "Execute a shell command.", ShellExecArgs, tags=["exec", "system"])
        ctx.tool_registry.register("git", git_tool, "Execute git commands.", GitArgs, tags=["git", "vcs"])
        ctx.tool_registry.register("doc_search", doc_search, "Search project documentation.", DocSearchArgs, tags=["read", "research"])
        ctx.tool_registry.register("request_clarification", request_clarification, "Ask the user for more information.", ClarificationArgs, tags=["comm", "interrupt"])
        ctx.tool_registry.register("code_search", code_search, "Search for a regex pattern across project files.", CodeSearchArgs, tags=["read", "research", "search"])
        ctx.tool_registry.register("file_patch", file_patch, "Apply a surgical text replacement in a file.", FilePatchArgs, tags=["write", "edit", "patch"])
        ctx.tool_registry.register("url_fetch", url_fetch, "Fetch a URL via HTTP GET with configurable timeout.", UrlFetchArgs, tags=["read", "network"])

        ctx.tool_defs = ctx.tool_registry.get_definitions(minimalist=True)

        # Set workspace root for sandboxed tool operations
        from src.tools.system_tools import set_workspace_root as _set_tools_root
        _set_tools_root(workspace_root)

        return ctx

    def add_runtime_services(self, memory, healer, web_client, chat, chat_context):
        """Set runtime services after bridge initialization."""
        self.memory = memory
        self.healer = healer
        self.web_client = web_client
        self.chat = chat
        self.chat_context = chat_context
