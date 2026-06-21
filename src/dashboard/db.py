"""Database path resolution for dashboard."""
import os
from pathlib import Path

WORKSPACE_ROOT = Path(os.getenv("WW_WORKSPACE", os.getcwd()))


def get_db_path() -> Path:
    """Get telemetry database path."""
    try:
        from src.config import get_settings
        settings = get_settings()
        workspace = settings.resolve_workspace()
        return workspace / ".tel" / "telemetry.db"
    except Exception:
        return WORKSPACE_ROOT / ".tel" / "telemetry.db"


def get_memory_db_path() -> Path:
    """Get sessions/memory database path."""
    try:
        from src.config import get_settings
        settings = get_settings()
        workspace = settings.resolve_workspace()
        return workspace / ".tel" / "sessions" / "sessions.db"
    except Exception:
        return WORKSPACE_ROOT / ".tel" / "sessions" / "sessions.db"
