"""
BridgeContext — centralized state container for the WW Bridge.

Replaces module-level mutable singletons with a single dataclass
that is explicitly constructed and passed to subsystems.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict

from src.config import Settings
# from src.core.context import ConversationHistory, TokenCounter
from src.security import PermissionManager
from src.checkpoint import CheckpointManager
from src.diff_engine import DiffEngine
from src.observability import TelemetryManager
from src.core.memory import MemoryManager
from src.core.healing import AutoHealer
from src.core.patterns.causal_graph import CausalGraph
from src.tools.registry import ToolRegistry
from src.tools.system_tools import (
    read_file, list_dir, write_file, shell_exec, git_tool,
    doc_search, request_clarification, code_search, file_patch, url_fetch,
    ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs,
    GitArgs, DocSearchArgs, ClarificationArgs,
    CodeSearchArgs, FilePatchArgs, UrlFetchArgs
)
from src.security import ApprovalPolicy
from src.core.utils.web_client import WebGeminiClient


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
"""
Context Window Management with Token Counting and Auto-Compaction.

Frontier-grade context management inspired by Claude Code and Codex CLI.
Tracks token usage across conversation turns, triggers automatic compaction
when approaching the context window limit, and provides a repo-map style
structural overview using AST-aware parsing.
"""

import tiktoken
from loguru import logger
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import os
import subprocess
import re


from src.constants import BASE_IGNORE, CRITICAL_FILES, PARSEABLE_EXTENSIONS

# Default context window size for Gemini models
DEFAULT_CONTEXT_WINDOW = 128_000
COMPACTION_THRESHOLD = 0.75  # Trigger compaction at 75% utilization


class TokenCounter:
    """Counts tokens using tiktoken (cl100k_base as approximation for Gemini).
    
    Features LRU caching to avoid re-tokenizing the same text, and an
    incremental total that enables O(1) conversation-length updates.
    """

    def __init__(self, model: str = "cl100k_base"):
        self.encoder = tiktoken.get_encoding(model)
        self._cache = {}
        self._total = 0
        self._dirty = True

    def count(self, text: str) -> int:
        """Count tokens in a string (LRU-cached)."""
        if not text:
            return 0
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        result = len(self.encoder.encode(text))
        # LRU eviction at 128 entries
        if len(self._cache) >= 128:
            self._cache.pop(next(iter(self._cache)))
        self._cache[text] = result
        return result

    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens across a list of message dicts."""
        total = 0
        for msg in messages:
            total += self.count(msg.get("content", ""))
            total += 4  # Overhead per message (role tokens, separators)
        return total

    def invalidate_cache(self) -> None:
        """Clear the LRU cache (call after context compaction)."""
        self._cache.clear()
        self._dirty = True

    def incremental_add(self, text: str) -> int:
        """Add text to running total without re-computing history. O(1)."""
        self._total += self.count(text)
        return self._total

    def get_total(self) -> int:
        return self._total

    def reset_total(self) -> None:
        self._total = 0
        self._dirty = True


class ConversationHistory:
    """Manages conversation history with token-aware compaction."""

    def __init__(self, context_window: int = DEFAULT_CONTEXT_WINDOW):
        self.context_window = context_window
        self.threshold = int(context_window * COMPACTION_THRESHOLD)
        self.counter = TokenCounter()
        self.turns: List[Dict[str, str]] = []
        self.system_prompt_tokens: int = 0
        self.compaction_count: int = 0

    def set_system_prompt_tokens(self, tokens: int):
        """Record how many tokens the system prompt uses."""
        self.system_prompt_tokens = tokens

    def add_turn(self, role: str, content: str, tool_output: bool = False):
        """Add a conversation turn."""
        self.turns.append({
            "role": role,
            "content": content,
            "tokens": self.counter.count(content),
            "tool_output": tool_output,
        })

    def get_total_tokens(self) -> int:
        """Get total token count including system prompt."""
        turn_tokens = sum(t["tokens"] for t in self.turns)
        return self.system_prompt_tokens + turn_tokens

    def get_utilization(self) -> float:
        """Get context window utilization as a percentage."""
        return self.get_total_tokens() / self.context_window

    def needs_compaction(self) -> bool:
        """Check if compaction is needed."""
        return self.get_total_tokens() >= self.threshold

    def compact(self) -> str:
        """
        Compact the conversation history by summarizing older turns.

        Strategy (inspired by Claude Code):
        1. Preserve the most recent 4 turns (user + assistant pairs)
        2. Preserve all turns that contain critical instructions
        3. Summarize everything else into a dense recap
        4. Drop verbose tool outputs from older turns
        """
        if len(self.turns) <= 4:
            return "No compaction needed - conversation is short."

        # Split into older turns and recent turns
        recent_count = min(8, len(self.turns))
        older_turns = self.turns[:-recent_count]
        recent_turns = self.turns[-recent_count:]

        # Build a summary of older turns
        summary_parts = []
        user_requests = []
        key_results = []

        for turn in older_turns:
            if turn["role"] == "user" and not turn["tool_output"]:
                user_requests.append(turn["content"][:200])
            elif turn["role"] == "assistant" and not turn["tool_output"]:
                # Keep only the first 100 chars of assistant responses
                key_results.append(turn["content"][:100])

        if user_requests:
            summary_parts.append(
                "PREVIOUS USER REQUESTS:\n" +
                "\n".join(f"- {r}" for r in user_requests[-5:])
            )
        if key_results:
            summary_parts.append(
                "KEY RESULTS:\n" +
                "\n".join(f"- {r}" for r in key_results[-5:])
            )

        compacted_summary = (
            "=== COMPACTED CONVERSATION HISTORY ===\n"
            f"(Compaction #{self.compaction_count + 1}: "
            f"{len(older_turns)} older turns summarized)\n\n" +
            "\n\n".join(summary_parts) +
            "\n=== END COMPACTED HISTORY ===\n"
        )

        # Replace turns with compacted version
        summary_turn = {
            "role": "system",
            "content": compacted_summary,
            "tokens": self.counter.count(compacted_summary),
            "tool_output": False,
        }

        self.turns = [summary_turn] + recent_turns
        self.compaction_count += 1

        tokens_after = self.get_total_tokens()
        return (
            f"Compacted: {len(older_turns)} turns summarized. "
            f"Context now at {tokens_after}/{self.context_window} tokens "
            f"({self.get_utilization():.0%} utilization)."
        )

    def get_token_report(self) -> str:
        """Generate a human-readable token usage report."""
        total = self.get_total_tokens()
        util = self.get_utilization()
        bar_len = 30
        filled = int(bar_len * util)
        bar = "█" * filled + "░" * (bar_len - filled)

        return (
            f"[{bar}] {total:,}/{self.context_window:,} tokens ({util:.0%})\n"
            f"  System: {self.system_prompt_tokens:,} | "
            f"Turns: {len(self.turns)} | "
            f"Compactions: {self.compaction_count}"
        )


class RepoMapper:
    """
    Generates a structural map of the repository using symbol extraction.

    Inspired by Aider's Tree-sitter repo map, this provides the LLM with
    a concise overview of classes, functions, and their signatures without
    needing to read every file.
    """

    # File extensions we can parse for symbols
    PARSEABLE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java",
        ".go", ".rs", ".rb", ".c", ".cpp", ".h",
    }

    def __init__(self, workspace_root: Path, max_tokens: int = 2000):
        self.workspace_root = workspace_root
        self.max_tokens = max_tokens
        self.counter = TokenCounter()

    def _extract_python_symbols(self, filepath: Path) -> List[str]:
        """Extract class and function definitions from a Python file."""
        symbols = []
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            for i, line in enumerate(lines):
                stripped = line.rstrip()
                # Match class definitions
                if re.match(r'^class\s+\w+', stripped):
                    symbols.append(stripped)
                # Match top-level and method function definitions
                elif re.match(r'^(\s*)def\s+\w+', stripped):
                    symbols.append(stripped)
                # Match decorated functions/classes
                elif re.match(r'^(\s*)@\w+', stripped):
                    # Look ahead for the def/class
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].rstrip()
                        if re.match(r'^(\s*)(def|class)\s+\w+', next_line):
                            symbols.append(f"{stripped}\n{next_line}")
        except Exception:
            pass
        return symbols

    def _extract_js_symbols(self, filepath: Path) -> List[str]:
        """Extract function/class/export definitions from JS/TS files."""
        symbols = []
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()

            for line in lines:
                stripped = line.rstrip()
                if re.match(r'^(export\s+)?(class|function|const|interface|type)\s+\w+', stripped):
                    symbols.append(stripped[:120])
                elif re.match(r'^\s*(async\s+)?function\s+\w+', stripped):
                    symbols.append(stripped[:120])
        except Exception:
            pass
        return symbols

    def _extract_symbols(self, filepath: Path) -> List[str]:
        """Extract symbols based on file extension."""
        ext = filepath.suffix.lower()
        if ext == ".py":
            return self._extract_python_symbols(filepath)
        elif ext in {".js", ".ts", ".jsx", ".tsx"}:
            return self._extract_js_symbols(filepath)
        return []

    def generate_map(self, focus_files: Optional[List[Path]] = None) -> str:
        """
        Generate a concise repository map showing key symbols.

        Args:
            focus_files: If provided, prioritize these files in the map.
        """
        import pathspec

        # Load .gitignore
        gitignore = self.workspace_root / ".gitignore"
        patterns = []
        if gitignore.exists():
            patterns = gitignore.read_text().splitlines()
        spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

        base_ignore = {".git", "node_modules", "__pycache__", "venv", ".venv", ".logs"}

        map_parts = ["REPOSITORY MAP (key symbols):"]
        total_tokens = 0

        # Collect all parseable files
        all_files = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in base_ignore]
            rel_root = os.path.relpath(root, self.workspace_root)

            for f in sorted(files):
                rel_path = os.path.join(rel_root, f) if rel_root != "." else f
                if spec.match_file(rel_path):
                    continue
                filepath = Path(root) / f
                if filepath.suffix.lower() in self.PARSEABLE_EXTENSIONS:
                    all_files.append(filepath)

        # Prioritize focus files
        if focus_files:
            focus_set = set(str(f.resolve()) for f in focus_files)
            all_files.sort(key=lambda f: (0 if str(f.resolve()) in focus_set else 1, str(f)))

        for filepath in all_files:
            symbols = self._extract_symbols(filepath)
            if not symbols:
                continue

            rel_path = filepath.relative_to(self.workspace_root)
            file_section = f"\n{rel_path}:\n" + "\n".join(f"  {s}" for s in symbols[:15])

            section_tokens = self.counter.count(file_section)
            if total_tokens + section_tokens > self.max_tokens:
                map_parts.append(f"\n... (map truncated at {self.max_tokens} token budget)")
                break

            map_parts.append(file_section)
            total_tokens += section_tokens

        return "\n".join(map_parts)
"""
Smart Context Gathering with Git-Awareness and Repo Mapping.

Enhanced workspace context engine that provides:
- .gitignore-aware file tree
- Intelligent file truncation (head + tail)
- AST-aware repository map for structural understanding
- Token-budget-aware context sizing
"""

from src.core.context import RepoMapper
import os
from pathlib import Path
from typing import List, Set, Optional
import pathspec

from src.constants import BASE_IGNORE, CRITICAL_FILES, MAX_FILE_LINES_DEFAULT, MAX_FILE_LINES_CRITICAL, MAX_TREE_LINES



def get_gitignore_spec(root: Path):
    """Loads .gitignore and returns a pathspec object."""
    gitignore = root / ".gitignore"
    patterns = []
    if gitignore.exists():
        try:
            patterns = gitignore.read_text().splitlines()
        except (OSError, PermissionError) as e:
            import warnings
            warnings.warn(f"Could not read .gitignore: {e}")
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)


def is_binary(p: Path) -> bool:
    """Check if a file is likely binary."""
    try:
        with open(p, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True


def read_file_surgical(p: Path, max_lines: int = 150, max_size_kb: int = 10240) -> str:
    """
    Reads a file with smart truncation (head and tail preservation).

    - Skips binary files
    - Skips files larger than max_size_kb (default 10MB) to avoid memory spikes
    - Uses lazy line iteration — never loads the full file into memory
    - Uses fast newline-counting via 8KB buffered reads instead of line-by-line
    
    For log files, preserves the tail. For source files, preserves
    the head and tail with a truncation marker in the middle.
    """
    if is_binary(p):
        return f"[BINARY FILE: {p.name} - cannot display as text]"
    try:
        # Fast size check — skip files over threshold
        file_size = p.stat().st_size
        if file_size > max_size_kb * 1024:
            return f"[FILE TOO LARGE: {p.name} ({file_size // 1024} KB) — skipped]\n"
        
        # Fast line count: read in 8KB chunks, count newlines
        total_lines = 0
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                total_lines += chunk.count(b"\n")
        
        if total_lines <= max_lines:
            return p.read_text(encoding="utf-8", errors="ignore")
        
        half = max_lines // 2
        from collections import deque

        # For log files, show the tail
        if p.suffix in {".log", ".out"}:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                tail = deque(f, max_lines)
            return (
                f"[... {total_lines - max_lines} lines omitted (showing tail) ...]\n"
                + "".join(tail)
            )

        # For source files, show head + tail
        head_lines = []
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= half:
                    break
                head_lines.append(line)
        
        tail_lines_list = []
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            tail_lines_list = list(deque(f, half))
        
        return (
            "".join(head_lines)
            + f"\n[... {total_lines - max_lines} lines omitted ...]\n"
            + "".join(tail_lines_list)
        )
    except Exception as e:
        return f"[ERROR READING FILE: {e}]\n"
def get_directory_context(path: Path, depth: int = 2) -> str:
    """Gathers detailed context for a specific directory."""
    if not path.exists() or not path.is_dir():
        return f"ERROR: Directory {path} does not exist."

    tree_lines = [f"Detailed Structure for {path.name}/:"]
    for r, dirs, files in os.walk(path):
        rel_r = os.path.relpath(r, path)
        level = 0 if rel_r == "." else rel_r.count(os.sep) + 1
        if level > depth:
            continue

        dirs[:] = [d for d in dirs if d not in BASE_IGNORE]

        indent = "  " * level
        if rel_r != ".":
            tree_lines.append(f"{indent}{os.path.basename(r)}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            tree_lines.append(f"{sub_indent}{f}")

    return "\n".join(tree_lines)


def get_workspace_context(root_path: str = ".", max_tree_lines: int = MAX_TREE_LINES) -> str:
    """
    Intelligently gathers workspace context using .gitignore and focused logic.

    Enhanced with:
    - Repo map integration for structural understanding
    - Token-aware sizing
    - Better file categorization
    """
    root = Path(root_path).resolve()
    spec = get_gitignore_spec(root)
    context_parts = []

    # 1. Critical configuration files (AGENTS.md, README, etc.)
    critical_content = []
    for cf in CRITICAL_FILES:
        p = root / cf
        if p.exists() and p.is_file():
            content = read_file_surgical(p, max_lines=MAX_FILE_LINES_CRITICAL)
            critical_content.append(f"### {cf}\n```\n{content}\n```")

    if critical_content:
        context_parts.append(
            "## Critical Configuration & Metadata\n" + "\n\n".join(critical_content)
        )

    # 2. Optimized Tree (Respecting .gitignore)
    tree_lines = []
    for r, dirs, files in os.walk(root):
        rel_r = os.path.relpath(r, root)

        # Filter directories
        dirs[:] = sorted([
            d for d in dirs
            if d not in BASE_IGNORE and not spec.match_file(
                os.path.join(rel_r, d) if rel_r != "." else d
            )
        ])

        level = 0 if rel_r == "." else rel_r.count(os.sep) + 1
        indent = "  " * level
        if rel_r != ".":
            tree_lines.append(f"{indent}{os.path.basename(r)}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            rel_f = os.path.join(rel_r, f) if rel_r != "." else f
            if not spec.match_file(rel_f) and f not in BASE_IGNORE:
                tree_lines.append(f"{sub_indent}{f}")

        # Prevent tree from getting too large
        if len(tree_lines) > max_tree_lines:
            tree_lines.append(
                f"{sub_indent}... (tree truncated at {max_tree_lines} lines, "
                "use 'tool:list' or 'tool:focus' for details)"
            )
            break

    context_parts.append(
        "## Project Structure\n```\n" + "\n".join(tree_lines) + "\n```"
    )

    # 3. Repository Map (AST-aware symbols)
    try:
        mapper = RepoMapper(root, max_tokens=1500)
        repo_map = mapper.generate_map()
        if repo_map and len(repo_map) > 50:
            context_parts.append(f"## Repository Map\n```\n{repo_map}\n```")
    except Exception:
        pass  # RepoMapper may fail on some workspaces

    # 4. Git status (if available)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            context_parts.append(
                f"## Git Status (uncommitted changes)\n```\n{result.stdout.strip()}\n```"
            )

        # Recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            context_parts.append(
                f"## Recent Commits\n```\n{result.stdout.strip()}\n```"
            )
    except Exception:
        pass

    final_context = (
        "--- Workspace Context ---\n"
        "NOTE: This is a high-level summary. Use 'tool:read', 'tool:list', "
        "'tool:search', or 'tool:focus' to explore specific paths.\n\n"
        + "\n\n".join(context_parts)
        + "\n\n--- End Context ---\n"
    )
    return final_context
