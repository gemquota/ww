"""WW Python package.

Core imports stay deliberately inert. Legacy/advanced components are exposed
lazily for compatibility, so importing the basic Gemini terminal does not
initialize the agent framework or pull in its optional dependencies.
"""
from __future__ import annotations

from importlib import import_module

__version__ = "0.3.0"
__author__ = "WW Team"
__description__ = "Minimal Gemini Web Chat terminal with optional extensions"

_EXPORTS = {
    "ToolCall": ("src.core.schemas", "ToolCall"),
    "MemoryManager": ("src.core.memory", "MemoryManager"),
    "SessionDatabase": ("src.core.memory", "SessionDatabase"),
    "MemoryEvent": ("src.core.memory", "MemoryEvent"),
    "AutoHealer": ("src.core.healing", "AutoHealer"),
    "BenchmarkHarness": ("src.core.benchmarker", "BenchmarkHarness"),
    "ExecutionTrace": ("src.core.benchmarker", "ExecutionTrace"),
    "BenchmarkResult": ("src.core.benchmarker", "BenchmarkResult"),
    "BenchmarkJudge": ("src.core.judge", "BenchmarkJudge"),
    "ToolRegistry": ("src.tools.registry", "ToolRegistry"),
    "ToolNode": ("src.tools.registry", "ToolNode"),
    "read_file": ("src.tools.system_tools", "read_file"),
    "write_file": ("src.tools.system_tools", "write_file"),
    "list_dir": ("src.tools.system_tools", "list_dir"),
    "shell_exec": ("src.tools.system_tools", "shell_exec"),
    "git_tool": ("src.tools.system_tools", "git_tool"),
    "doc_search": ("src.tools.system_tools", "doc_search"),
    "request_clarification": ("src.tools.system_tools", "request_clarification"),
    "code_search": ("src.tools.system_tools", "code_search"),
    "file_patch": ("src.tools.system_tools", "file_patch"),
    "url_fetch": ("src.tools.system_tools", "url_fetch"),
    "WebGeminiClient": ("src.utils.web_client", "WebGeminiClient"),
    "get_web_client": ("src.utils.web_client", "get_web_client"),
    "extract_tool_call": ("src.utils.validation", "extract_tool_call"),
    "Settings": ("src.config", "Settings"),
    "get_settings": ("src.config", "get_settings"),
    "reload_settings": ("src.config", "reload_settings"),
    "ConversationHistory": ("src.context_manager", "ConversationHistory"),
    "TokenCounter": ("src.context_manager", "TokenCounter"),
    "RepoMapper": ("src.context_manager", "RepoMapper"),
    "get_workspace_context": ("src.smart_context", "get_workspace_context"),
    "read_file_surgical": ("src.smart_context", "read_file_surgical"),
    "PermissionManager": ("src.permissions", "PermissionManager"),
    "ApprovalPolicy": ("src.permissions", "ApprovalPolicy"),
    "Sandbox": ("src.permissions", "Sandbox"),
    "DiffEngine": ("src.diff_engine", "DiffEngine"),
    "CheckpointManager": ("src.checkpoint", "CheckpointManager"),
    "load_all_instructions": ("src.agents_loader", "load_all_instructions"),
    "TelemetryManager": ("src.telemetry", "TelemetryManager"),
}


def __getattr__(name: str):
    """Load optional legacy exports only when explicitly requested."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


__all__ = list(_EXPORTS)
