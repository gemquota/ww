"""
WW Bridge — Gemini Multi-Agent Coding Harness.

A production-quality agentic coding loop providing:
- Token-aware context window management
- Fuzzy SEARCH/REPLACE editing with colorized diffs
- Granular permission/approval system for tool execution
- Git checkpoint system with /undo support
- AGENTS.md standard instruction loading
- AST-aware repository mapping
- SQLite-persisted multi-tier memory with PCG causal graphs
- FastAPI dashboard for session history and telemetry
- Hot-path performance profiling
"""

__version__ = "0.2.0"
__author__ = "WW Team"
__description__ = "Gemini Multi-Agent Bridge — Frontier-grade agentic coding harness"

# Core subsystems
from src.core.schemas import ToolCall
from src.core.memory import MemoryManager, SessionDatabase, MemoryEvent
from src.core.healing import AutoHealer
#
#

# Tools
from src.tools.registry import ToolRegistry, ToolNode
from src.tools.system_tools import (
    read_file, write_file, list_dir, shell_exec, git_tool,
    doc_search, request_clarification, code_search, file_patch, url_fetch,
)

# Utils
from src.core.utils.web_client import WebGeminiClient, get_web_client
from src.core.utils.validation import extract_tool_call

# Config
from src.config import Settings, get_settings, reload_settings

# Context
from src.core.context import ConversationHistory, TokenCounter, RepoMapper
from src.core.context import get_workspace_context, read_file_surgical

# Security
from src.security import PermissionManager, ApprovalPolicy, Sandbox

# Editing
from src.diff_engine import DiffEngine

# State
from src.checkpoint import CheckpointManager

# Instructions
from src.agents_loader import load_all_instructions

# Telemetry
from src.observability import TelemetryManager

__all__ = [
    "ToolCall", "MemoryManager", "SessionDatabase", "MemoryEvent",
    "AutoHealer",
    "ToolRegistry", "ToolNode",
    "read_file", "write_file", "list_dir", "shell_exec", "git_tool",
    "doc_search", "request_clarification", "code_search", "file_patch", "url_fetch",
    "WebGeminiClient", "get_web_client", "extract_tool_call",
    "Settings", "get_settings", "reload_settings",
    "ConversationHistory", "TokenCounter", "RepoMapper",
    "get_workspace_context", "read_file_surgical",
    "PermissionManager", "ApprovalPolicy", "Sandbox",
    "DiffEngine", "CheckpointManager", "load_all_instructions",
    "TelemetryManager",
]
