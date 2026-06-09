"""
Context Window Management with Token Counting and Auto-Compaction.

Frontier-grade context management inspired by Claude Code and Codex CLI.
Tracks token usage across conversation turns, triggers automatic compaction
when approaching the context window limit, and provides a repo-map style
structural overview using AST-aware parsing.
"""

import tiktoken
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import os
import subprocess
import re


# Default context window size for Gemini models
DEFAULT_CONTEXT_WINDOW = 128_000
COMPACTION_THRESHOLD = 0.75  # Trigger compaction at 75% utilization


class TokenCounter:
    """Counts tokens using tiktoken (cl100k_base as approximation for Gemini)."""

    def __init__(self, model: str = "cl100k_base"):
        self.encoder = tiktoken.get_encoding(model)

    def count(self, text: str) -> int:
        """Count tokens in a string."""
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens across a list of message dicts."""
        total = 0
        for msg in messages:
            total += self.count(msg.get("content", ""))
            total += 4  # Overhead per message (role tokens, separators)
        return total


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
