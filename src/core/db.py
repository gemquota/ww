"""Shared database connection management — SPA Phase 6 consolidation."""
import sqlite3
from pathlib import Path
from typing import Optional


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Get a SQLite connection with recommended settings."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def check_db_integrity(db_path: Path) -> dict:
    """Run integrity check on a database."""
    if not db_path.exists():
        return {"exists": False, "integrity_ok": False}
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        return {"exists": True, "integrity_ok": result == "ok", "size_bytes": db_path.stat().st_size}
    except sqlite3.DatabaseError as e:
        return {"exists": True, "integrity_ok": False, "error": str(e)}


def get_table_info(db_path: Path) -> list:
    """Get table information from a database."""
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [{"name": row[0], "sql": row[1]} for row in cursor.fetchall()]
        conn.close()
        return tables
    except sqlite3.DatabaseError:
        return []
