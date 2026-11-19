"""Workspace-local database path resolution for the dashboard."""
import os
from pathlib import Path


def workspace_root() -> Path:
    """Resolve the workspace at call time so .env and process overrides are honored."""
    return Path(os.getenv("WW_WORKSPACE", os.getcwd())).expanduser().resolve()


def get_db_path() -> Path:
    """Return the telemetry database path inside the configured workspace."""
    return workspace_root() / ".tel" / "telemetry.db"


def get_memory_db_path() -> Path:
    """Return the session/memory database path inside the configured workspace."""
    return workspace_root() / ".tel" / "sessions" / "sessions.db"
