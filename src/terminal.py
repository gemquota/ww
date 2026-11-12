"""Small, dependency-free terminal input helpers for WW."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

COMMANDS = (
    "/artifacts", "/canvas", "/chats", "/clear", "/context", "/copy",
    "/customize", "/doctor", "/exit", "/folder", "/folders", "/gems",
    "/help", "/history", "/image", "/last", "/model", "/models", "/music",
    "/new", "/open", "/quit", "/repeat", "/research", "/search", "/status",
    "/stream", "/video",
)


def history_path() -> Path:
    """Return the private, local prompt-history file."""
    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "ww" / "history"


def configure_line_editor() -> tuple[Any | None, Path]:
    """Load readline history and install slash-command tab completion when available."""
    path = history_path()
    try:
        import readline
    except ImportError:
        return None, path

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(str(path))
    except FileNotFoundError:
        pass
    except OSError:
        # A damaged or inaccessible history file must not prevent chat startup.
        pass
    readline.set_history_length(5000)
    readline.set_completer_delims(" \t\n")
    readline.set_completer(_command_completer)
    try:
        readline.parse_and_bind("tab: complete")
    except (AttributeError, OSError):
        pass
    return readline, path


def _command_completer(text: str, state: int) -> str | None:
    """Complete command names only at the start of an input line."""
    if not text.startswith("/"):
        return None
    matches = [command for command in COMMANDS if command.startswith(text.lower())]
    return matches[state] if state < len(matches) else None


def save_line_history(readline_module: Any | None, path: Path) -> None:
    """Persist readline history with owner-only permissions where supported."""
    if readline_module is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        readline_module.write_history_file(str(path))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError:
        pass


def get_line_history(readline_module: Any | None, fallback: list[str]) -> list[str]:
    """Return a copy of the active session's input history."""
    if readline_module is not None:
        try:
            return [
                value for index in range(1, readline_module.get_current_history_length() + 1)
                if (value := readline_module.get_history_item(index)) is not None
            ]
        except (AttributeError, OSError):
            pass
    return list(fallback)


def search_line_history(
    history: list[str], query: str, *, limit: int = 20
) -> list[tuple[int, str]]:
    """Find recent matching history entries, newest first, with stable 1-based indexes."""
    needle = query.casefold().strip()
    matches = [
        (index, value)
        for index, value in enumerate(history, 1)
        if needle in value.casefold()
    ]
    return list(reversed(matches[-max(1, limit):]))
