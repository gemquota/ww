from loguru import logger
import os
import sqlite3
import datetime
import threading
import time
import json
from pathlib import Path


def _crash_safe_commit(conn) -> None:
    """Commit and fsync for crash-safe persistence."""
    import os
    conn.commit()
    try:
        db_path = conn.execute("PRAGMA database_list").fetchone()[2]
        if db_path:
            fd = os.open(db_path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except Exception:
        pass  # fsync is best-effort


class TelemetryManager:
    # Tool calls whose arguments should be redacted in telemetry logs
    SENSITIVE_TOOLS = {"shell_exec", "url_fetch", "git_tool", "write_file"}
    
    def _redact_args(self, content: str) -> str:
        """Redact sensitive tool arguments to prevent credential leakage in logs."""
        import re
        for tool in self.SENSITIVE_TOOLS:
            # Match tool:xxx blocks and redact the args section
            pattern = re.compile(
                rf'(tool:{tool}\s*\n)(.*?)(?=\ntool:|\Z)',
                re.DOTALL
            )
            content = pattern.sub(
                lambda m: m.group(1) + "  args: [REDACTED]",
                content
            )
        return content

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        # Use data_dir from config, but always relative to the provided workspace_root
        try:
            from src.config import get_settings
            data_dir = get_settings().data_dir
        except Exception:
            data_dir = ".tel"
        self.logs_dir = workspace_root / data_dir
        self.sessions_dir = self.logs_dir / "sessions"
        self.prompts_dir = self.logs_dir / "prompts"
        self.db_path = self.logs_dir / "telemetry.db"
        # Shared connection must be initialized BEFORE _init_db()
        self._shared_conn = None
        self._conn_lock = threading.Lock()
        
        self._init_dirs()
        self._init_db()
        
        self.session_id = None
        self.session_log_path = None # .log file (human readable)
        self.session_jsonl_path = None # .jsonl file (structured)
        self.interaction_history = []

    def _init_dirs(self):
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_timestamp TEXT,
                end_timestamp TEXT,
                summary TEXT,
                log_file_path TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                timestamp TEXT,
                role TEXT,
                content TEXT,
                type TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        _crash_safe_commit(conn)
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or reuse a shared SQLite connection with retry for SQLITE_BUSY."""
        with self._conn_lock:
            if self._shared_conn is not None:
                try:
                    self._shared_conn.execute("SELECT 1")
                    return self._shared_conn
                except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                    pass
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA wal_autocheckpoint=1000")
            self._shared_conn = conn
            return conn

    def start_session(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_log_path = self.sessions_dir / f"session_{timestamp}.log"
        self.session_jsonl_path = self.sessions_dir / f"session_{timestamp}.jsonl"
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sessions (start_timestamp, log_file_path) VALUES (?, ?)", 
                       (timestamp, str(self.session_log_path)))
        self.session_id = cursor.lastrowid
        _crash_safe_commit(conn)
        conn.close()
        
        with open(self.session_log_path, "a") as f:
            f.write(f"=== SESSION START: {timestamp} ===\n")

    def log_interaction(self, role: str, content: str, msg_type: str = "text"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Redact sensitive tool arguments before logging
        content = self._redact_args(content)
        
        # Save to database
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO interactions (session_id, timestamp, role, content, type) VALUES (?, ?, ?, ?, ?)",
                       (self.session_id, timestamp, role, content, msg_type))
        _crash_safe_commit(conn)
        conn.close()
        
        # Save to session log (human)
        if self.session_log_path:
            with open(self.session_log_path, "a") as f:
                f.write(f"[{timestamp}] {role.upper()}: {content}\n\n")
            
        # Save to structured JSONL
        if self.session_jsonl_path:
            with open(self.session_jsonl_path, "a") as f:
                entry = {
                    "timestamp": timestamp,
                    "role": role,
                    "type": msg_type,
                    "content": content
                }
                f.write(json.dumps(entry) + "\n")
            
        # Collate individual prompts monthly
        if role.lower() == "user":
            month_str = datetime.datetime.now().strftime("%Y-%m")
            prompt_file = self.prompts_dir / f"prompts_{month_str}.log"
            with open(prompt_file, "a") as f:
                f.write(f"--- Prompt {timestamp} ---\n{content}\n\n")
        
        # Track in-memory with bounded size (last 200 entries)
        self.interaction_history.append({"role": role, "content": content[:500], "type": msg_type})
        if len(self.interaction_history) > 200:
            self.interaction_history = self.interaction_history[-200:]

    def export_markdown(self):
        """Export the current session to a Markdown file in .logs/prompts/."""
        if not self.session_id:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        md_path = self.prompts_dir / f"session_{timestamp}.md"
        with open(md_path, "w") as f:
            f.write(f"# WW Session Export\n\n")
            f.write(f"**Date**: {timestamp}\n")
            f.write(f"**Session ID**: {self.session_id}\n\n")
            f.write(f"## Conversation Log\n\n")
            for entry in self.interaction_history:
                role = entry.get("role", "unknown").upper()
                content = entry.get("content", "")
                f.write(f"### [{role}]\n\n")
                f.write(f"```\n{content}\n```\n\n")
            f.write(f"---\n*End of session export.*\n")
        logger.info(f"Session exported to {md_path}")
        return md_path

    def _check_last_session_end(self) -> bool:
        """Check if the last session ended properly (has end_timestamp).
        Returns True if last session is clean, False if interrupted, None if no sessions exist."""
        import sqlite3
        try:
            conn = self._get_conn()
            cursor = conn.execute("SELECT end_timestamp FROM sessions ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row is None:
                return None
            return row[0] is not None
        except Exception:
            return None

    def end_session(self, summary: str = "No summary provided"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET end_timestamp = ?, summary = ? WHERE id = ?",
                       (timestamp, summary, self.session_id))
        _crash_safe_commit(conn)
        conn.close()
        
        if self.session_log_path:
            with open(self.session_log_path, "a") as f:
                f.write(f"\nSUMMARY: {summary}\n")
                f.write(f"=== SESSION END: {timestamp} ===\n")
            
        # Final JSONL summary
        if self.session_jsonl_path:
            with open(self.session_jsonl_path, "a") as f:
                summary_entry = {
                    "timestamp": timestamp,
                    "type": "summary",
                    "summary": summary
                }
                f.write(json.dumps(summary_entry) + "\n")

class ActivationFunnel:
    """Track activation funnel: install -> first query -> return -> retention."""

    def __init__(self, workspace_root):
        Path(workspace_root).joinpath(".tel").mkdir(parents=True, exist_ok=True)
        self.db_path = Path(workspace_root) / ".tel" / "telemetry.db"
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS activation_funnel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def track(self, event: str, metadata: dict = None):
        """Track an activation event."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO activation_funnel (event, timestamp, metadata) VALUES (?, ?, ?)",
                (event, time.time(), json.dumps(metadata or {}))
            )
            conn.commit()
        finally:
            conn.close()

    def get_metrics(self) -> dict:
        """Get activation funnel metrics."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            total = conn.execute("SELECT COUNT(*) FROM activation_funnel").fetchone()[0]
            first_query = conn.execute(
                "SELECT COUNT(*) FROM activation_funnel WHERE event='first_query'"
            ).fetchone()[0]
            returned = conn.execute(
                "SELECT COUNT(*) FROM activation_funnel WHERE event='return_24h'"
            ).fetchone()[0]
            return {
                "total_events": total,
                "first_queries": first_query,
                "returned_24h": returned,
                "conversion_rate": round(first_query / max(total, 1) * 100, 1)
            }
        finally:
            conn.close()


class TimeToValueTracker:
    """Track time-to-value: first launch to first successful tool execution."""

    def __init__(self, workspace_root):
        Path(workspace_root).joinpath(".tel").mkdir(parents=True, exist_ok=True)
        self.db_path = Path(workspace_root) / ".tel" / "telemetry.db"
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ttv_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    session_id TEXT DEFAULT ''
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def track(self, event: str, session_id: str = ""):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO ttv_events (event, timestamp, session_id) VALUES (?, ?, ?)",
                (event, time.time(), session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_median_ttv(self) -> float:
        """Get median time from first_launch to first_tool_exec."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            launches = conn.execute(
                "SELECT timestamp FROM ttv_events WHERE event='first_launch' ORDER BY timestamp"
            ).fetchall()
            first_tools = conn.execute(
                "SELECT timestamp FROM ttv_events WHERE event='first_tool_exec' ORDER BY timestamp"
            ).fetchall()
            if launches and first_tools:
                times = []
                for l in launches:
                    match_t = [t[0] for t in first_tools if t[0] > l[0]]
                    if match_t:
                        times.append(match_t[0] - l[0])
                if times:
                    times.sort()
                    return times[len(times) // 2]
            return 0.0
        finally:
            conn.close()


class FeatureDiscovery:
    """Progressive feature discovery based on usage patterns."""

    FEATURES = [
        (3, "/undo - Revert changes with a checkpoint"),
        (5, "--verbose mode for detailed operation logs"),
        (10, "/save and /load for session persistence"),
        (15, "--script mode for automated workflows"),
        (25, "Plugin system for custom extensions"),
    ]

    def __init__(self, workspace_root):
        Path(workspace_root).joinpath(".tel").mkdir(parents=True, exist_ok=True)
        self.db_path = Path(workspace_root) / ".tel" / "telemetry.db"
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feature_discovery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature TEXT NOT NULL,
                    suggested_at REAL,
                    adopted INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_next_suggestion(self, task_count: int) -> str:
        """Get the next feature suggestion based on task count."""
        for threshold, feature in self.FEATURES:
            if task_count >= threshold:
                return f"Tip: Try {feature}"
        return ""
