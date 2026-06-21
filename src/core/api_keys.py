"""
Self-service API key management — NEW-F1#4 (Naomi Chen).
"""
import secrets
import hashlib
import sqlite3
import time
from typing import Optional, Dict, Any
from pathlib import Path


class APIKeyManager:
    """SQLite-backed API key store with create/rotate/revoke."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT UNIQUE NOT NULL,
                    prefix TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT 'default',
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    revoked INTEGER DEFAULT 0,
                    last_used_at REAL,
                    permissions TEXT DEFAULT 'read'
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def create_key(self, name: str = "default",
                   expires_in_days: Optional[int] = None,
                   permissions: str = "read") -> Dict[str, Any]:
        """Create a new API key. Returns the full key (only shown once)."""
        prefix = "ww_" + secrets.token_hex(4)
        key = prefix + "_" + secrets.token_hex(24)
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        expires_at = (time.time() + expires_in_days * 86400) if expires_in_days else None

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO api_keys (key_hash, prefix, name, created_at, expires_at, permissions) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key_hash, prefix, name, time.time(), expires_at, permissions)
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "key": key,
            "prefix": prefix,
            "name": name,
            "created_at": time.time(),
            "expires_at": expires_at,
            "permissions": permissions,
            "warning": "Store this key securely. It will not be shown again."
        }

    def validate_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key. Returns key info or None."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT id, prefix, name, created_at, expires_at, revoked, permissions "
                "FROM api_keys WHERE key_hash = ?", (key_hash,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            key_id, prefix, name, created_at, expires_at, revoked, permissions = row

            if revoked:
                return None
            if expires_at and time.time() > expires_at:
                return None

            # Update last used
            conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                         (time.time(), key_id))
            conn.commit()

            return {
                "id": key_id,
                "prefix": prefix,
                "name": name,
                "created_at": created_at,
                "expires_at": expires_at,
                "permissions": permissions,
            }
        finally:
            conn.close()

    def revoke_key(self, prefix: str) -> bool:
        """Revoke a key by its prefix."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE prefix = ?", (prefix,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_keys(self) -> list:
        """List all non-revoked keys (without the secret)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT prefix, name, created_at, expires_at, last_used_at, permissions "
                "FROM api_keys WHERE revoked = 0 ORDER BY created_at DESC"
            )
            return [dict(zip(["prefix", "name", "created_at", "expires_at",
                              "last_used_at", "permissions"], row))
                    for row in cursor.fetchall()]
        finally:
            conn.close()
