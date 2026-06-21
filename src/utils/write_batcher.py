"""
Unified write-batcher for coalescing SQLite writes.
Addresses NEW-B1#3 (Lin Wei).
"""
import time
import sqlite3
import threading
from typing import List, Callable, Tuple, Optional
from pathlib import Path


class WriteBatcher:
    """Coalesces writes within a time window into a single transaction."""

    def __init__(self, db_path: Path, window_ms: int = 100):
        self.db_path = db_path
        self.window = window_ms / 1000.0
        self._queue: List[Tuple[str, tuple]] = []
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def enqueue(self, sql: str, params: tuple = ()):
        """Queue a write for batched execution."""
        with self._lock:
            self._queue.append((sql, params))
            if self._timer is None:
                self._timer = threading.Timer(self.window, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self):
        """Execute all queued writes in a single transaction."""
        with self._lock:
            queue = self._queue[:]
            self._queue.clear()
            self._timer = None

        if not queue:
            return

        try:
            conn = self._get_conn()
            conn.execute("BEGIN")
            for sql, params in queue:
                conn.execute(sql, params)
            conn.commit()
        except Exception as e:
            # Re-queue on failure
            with self._lock:
                self._queue = queue + self._queue

    def flush_now(self):
        """Force immediate flush of queued writes."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._flush()

    def close(self):
        """Flush and close connection."""
        self.flush_now()
        if self._conn:
            self._conn.close()
            self._conn = None
