"""Metrics tracking for development lifecycle."""
import time
import sqlite3
from pathlib import Path
from typing import Optional


class FirstCommitTracker:
    """Tracks time-to-first-commit for new developers."""

    def __init__(self, data_dir: str = ".tel"):
        self.db_path = Path.cwd() / data_dir / "metrics.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS first_commit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    developer_id TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    first_commit_time REAL,
                    first_commit_hash TEXT,
                    repo_url TEXT,
                    completed INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dev_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    developer_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    recorded_at REAL DEFAULT (julianday('now'))
                )
            """)

    def start_tracking(self, developer_id: str, repo_url: str = "") -> int:
        """Begin tracking a developer's time-to-first-commit."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO first_commit (developer_id, start_time, repo_url) VALUES (?, ?, ?)",
                (developer_id, time.time(), repo_url)
            )
            return cur.lastrowid

    def record_commit(self, tracking_id: int, commit_hash: str) -> bool:
        """Record when the first commit happens."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "UPDATE first_commit SET first_commit_time = ?, first_commit_hash = ?, completed = 1 WHERE id = ?",
                (time.time(), commit_hash, tracking_id)
            )
            return cur.rowcount > 0

    def get_time_to_first_commit(self, tracking_id: int) -> Optional[float]:
        """Get time-to-first-commit in seconds. Returns None if not yet committed."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT start_time, first_commit_time FROM first_commit WHERE id = ?",
                (tracking_id,)
            ).fetchone()
            if row and row[1]:
                return row[1] - row[0]
            return None

    def get_average_time(self) -> Optional[float]:
        """Get average time-to-first-commit across all completed developers."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT AVG(first_commit_time - start_time) FROM first_commit WHERE completed = 1"
            ).fetchone()
            return row[0] if row and row[0] else None

    def record_metric(self, developer_id: str, name: str, value: float):
        """Record an arbitrary development metric."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO dev_metrics (developer_id, metric_name, metric_value) VALUES (?, ?, ?)",
                (developer_id, name, value)
            )

    def get_metric(self, developer_id: str, name: str) -> Optional[float]:
        """Get the latest value for a metric."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT metric_value FROM dev_metrics WHERE developer_id = ? AND metric_name = ? ORDER BY id DESC LIMIT 1",
                (developer_id, name)
            ).fetchone()
            return row[0] if row else None
