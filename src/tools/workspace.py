"""Workspace root management."""
from pathlib import Path
from typing import Optional

_WORKSPACE_ROOT: Optional[Path] = None


def _get_workspace_root() -> Path:
    """Get the resolved workspace root, falling back to CWD."""
    global _WORKSPACE_ROOT
    if _WORKSPACE_ROOT is None:
        _WORKSPACE_ROOT = Path.cwd().resolve()
    return _WORKSPACE_ROOT


def set_workspace_root(path: Path) -> None:
    """Set the workspace root for sandboxed operations."""
    global _WORKSPACE_ROOT
    _WORKSPACE_ROOT = path.resolve()
