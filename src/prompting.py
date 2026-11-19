"""Prompt-toolkit configuration for WW's interactive terminal."""
from __future__ import annotations

import os
from pathlib import Path


COMMANDS = [
    "/new", "/context", "/status", "/doctor", "/chats", "/folders", "/folder",
    "/gems", "/customize", "/research", "/image", "/video", "/music", "/canvas",
    "/artifacts", "/open", "/help", "/exit", "/quit",
]


def history_file_path() -> Path:
    """Return the persistent WW prompt history path."""
    configured = os.getenv("WW_HISTORY_FILE")
    if configured:
        return Path(configured).expanduser()
    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "ww" / "history"


def create_terminal_session(**kwargs):
    """Create a multiline prompt with persistent history and command completion.

    Enter inserts a newline; Escape+Enter submits the complete buffer. The
    history location can be overridden with WW_HISTORY_FILE.
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory

    history_path = history_file_path()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("history", FileHistory(str(history_path)))
    kwargs.setdefault(
        "completer",
        WordCompleter(COMMANDS, ignore_case=True, sentence=True),
    )
    kwargs.setdefault("complete_while_typing", True)
    kwargs.setdefault("enable_history_search", True)
    return PromptSession(multiline=True, **kwargs)
