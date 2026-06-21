"""
Tamper-evident Merkle-chain for log entries.
Addresses NEW-V6-S1#1 (Detective Ava Chen).
"""
import hashlib
import json
import time
import sqlite3
from typing import Optional, List, Dict, Any
from pathlib import Path


class MerkleChain:
    """Append-only tamper-evident log chain using Merkle hashing."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    previous_hash TEXT NOT NULL DEFAULT '',
                    hash TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _get_last_hash(self) -> str:
        """Get the hash of the most recent entry."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT hash FROM log_chain ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else ""
        finally:
            conn.close()

    def _compute_hash(self, timestamp: float, event_type: str,
                      data: str, previous_hash: str) -> str:
        """Compute SHA-256 hash of a log entry."""
        content = f"{timestamp}|{event_type}|{data}|{previous_hash}"
        return hashlib.sha256(content.encode()).hexdigest()

    def append(self, event_type: str, data: Dict[str, Any]) -> str:
        """Append a log entry and return its hash."""
        previous_hash = self._get_last_hash()
        timestamp = time.time()
        data_str = json.dumps(data, sort_keys=True)
        entry_hash = self._compute_hash(timestamp, event_type, data_str, previous_hash)

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO log_chain (timestamp, event_type, data, previous_hash, hash) "
                "VALUES (?, ?, ?, ?, ?)",
                (timestamp, event_type, data_str, previous_hash, entry_hash)
            )
            conn.commit()
        finally:
            conn.close()

        return entry_hash

    def verify_integrity(self) -> bool:
        """Verify the entire chain integrity. Returns True if intact."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT id, timestamp, event_type, data, previous_hash, hash "
                "FROM log_chain ORDER BY id"
            ).fetchall()

            expected_prev = ""
            for row in rows:
                _, timestamp, event_type, data_str, prev_hash, entry_hash = row
                if prev_hash != expected_prev:
                    return False
                computed = self._compute_hash(timestamp, event_type, data_str, prev_hash)
                if computed != entry_hash:
                    return False
                expected_prev = entry_hash
            return True
        finally:
            conn.close()

    def get_entry(self, entry_hash: str) -> Optional[Dict]:
        """Get a log entry by its hash."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT timestamp, event_type, data, previous_hash, hash "
                "FROM log_chain WHERE hash = ?", (entry_hash,)
            ).fetchone()
            if row:
                return {
                    "timestamp": row[0],
                    "event_type": row[1],
                    "data": json.loads(row[2]),
                    "previous_hash": row[3],
                    "hash": row[4],
                }
            return None
        finally:
            conn.close()

    def get_chain_length(self) -> int:
        """Get the number of entries in the chain."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            return conn.execute("SELECT COUNT(*) FROM log_chain").fetchone()[0]
        finally:
            conn.close()


class AuditTrail:
    """Comprehensive audit trail — S1#2 (Detective Ava Chen).
    
    Wraps MerkleChain with structured event types and querying.
    Provides complete auditability of agent actions.
    """

    EVENT_TYPES = {
        "user_query": "User submitted query",
        "agent_response": "Agent generated response",
        "tool_execution": "Tool was executed",
        "tool_result": "Tool returned result",
        "permission_check": "Permission was checked",
        "permission_granted": "Permission was granted",
        "permission_denied": "Permission was denied",
        "file_read": "File was read",
        "file_write": "File was written",
        "file_patch": "File was patched",
        "shell_command": "Shell command executed",
        "memory_access": "Memory was accessed",
        "memory_write": "Memory was written",
        "checkpoint_created": "Checkpoint was created",
        "checkpoint_restored": "Checkpoint was restored",
        "session_start": "Session started",
        "session_end": "Session ended",
        "error": "Error occurred",
        "auth_success": "Authentication succeeded",
        "auth_failure": "Authentication failed",
    }

    def __init__(self, db_path: Path):
        self.chain = MerkleChain(db_path)

    def record(self, event_type: str, details: dict, session_id: str = "") -> str:
        """Record an audit event. Returns event hash."""
        assert event_type in self.EVENT_TYPES, f"Unknown event type: {event_type}"
        data = {
            "event": event_type,
            "description": self.EVENT_TYPES[event_type],
            "session_id": session_id,
            **details,
        }
        return self.chain.append(event_type, data)

    def record_tool_execution(self, tool: str, args: dict, result: str,
                              duration_ms: float, session_id: str = "") -> str:
        """Record a tool execution with full details."""
        return self.record("tool_execution", {
            "tool": tool,
            "args": args,
            "result_preview": str(result)[:200],
            "duration_ms": round(duration_ms, 1),
        }, session_id)

    def query_by_type(self, event_type: str, limit: int = 50) -> list:
        """Query audit entries by event type."""
        conn = sqlite3.connect(str(self.chain.db_path))
        try:
            rows = conn.execute(
                "SELECT timestamp, event_type, data, hash FROM log_chain "
                "WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit)
            ).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "event_type": r[1],
                    "data": json.loads(r[2]),
                    "hash": r[3],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def query_by_session(self, session_id: str, limit: int = 100) -> list:
        """Query audit entries by session ID."""
        conn = sqlite3.connect(str(self.chain.db_path))
        try:
            rows = conn.execute(
                "SELECT timestamp, event_type, data, hash FROM log_chain "
                "WHERE data LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{session_id}%", limit)
            ).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "event_type": r[1],
                    "data": json.loads(r[2]),
                    "hash": r[3],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def query_recent(self, limit: int = 50) -> list:
        """Get the most recent audit entries."""
        conn = sqlite3.connect(str(self.chain.db_path))
        try:
            rows = conn.execute(
                "SELECT timestamp, event_type, data, hash FROM log_chain "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "event_type": r[1],
                    "data": json.loads(r[2]),
                    "hash": r[3],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def verify_chain(self) -> dict:
        """Verify the full audit trail integrity."""
        valid = self.chain.verify_integrity()
        return {
            "valid": valid,
            "chain_length": self.chain.get_chain_length(),
            "status": "PASS" if valid else "TAMPERED",
        }

    def get_stats(self) -> dict:
        """Get audit trail statistics."""
        conn = sqlite3.connect(str(self.chain.db_path))
        try:
            total = conn.execute("SELECT COUNT(*) FROM log_chain").fetchone()[0]
            by_type = conn.execute(
                "SELECT event_type, COUNT(*) as c FROM log_chain GROUP BY event_type"
            ).fetchall()
            return {
                "total_entries": total,
                "by_type": {r[0]: r[1] for r in by_type},
                "verified": self.chain.verify_integrity(),
            }
        finally:
            conn.close()
