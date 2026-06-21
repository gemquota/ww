"""
CLI commands — /docs, /help, /salvage, etc.
Addresses NEW-V5-E2#3 — hover documentation (/docs command).
"""
import pydoc
import sys
from typing import Optional


def docs_command(symbol: str) -> str:
    """Look up documentation for a symbol using pydoc."""
    try:
        help_text = pydoc.render_doc(symbol, renderer=pydoc.plaintext)
        # Truncate to reasonable length
        if len(help_text) > 2000:
            help_text = help_text[:2000] + "\n... (truncated)"
        return help_text
    except Exception as e:
        return f"No documentation found for '{symbol}': {e}"


def help_command(topic: Optional[str] = None) -> str:
    """Built-in help system."""
    if not topic:
        return """
WW Bridge Commands:
  /help [topic]    Show this help or help for a topic
  /docs <symbol>   Show documentation for a Python symbol
  /undo            Undo last operation
  /save <name>     Save current session
  /load <name>     Load a saved session
  /salvage         Attempt to recover a corrupted session

Topics: tools, sessions, plugins, configuration, tutorial
"""
    topics = {
        "tools": "Tools: read_file, write_file, file_patch, shell_exec, code_search, url_fetch, git, doc_search",
        "sessions": "Sessions persist conversation history. Use /save and /load to manage them.",
        "plugins": "Plugins extend functionality. Place .py files in the plugins directory.",
        "configuration": "Configuration via .env file. See --help for all CLI options.",
        "tutorial": "Run with --demo for a guided walkthrough.",
    }
    return topics.get(topic, f"Unknown topic: {topic}")
