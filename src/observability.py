from loguru import logger
import os
import sqlite3
import datetime
import threading
import time
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


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


# ── Merged from metrics.py (# Metrics subsystem) ──
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


# ── Merged from logchain.py (# Log chain) ──
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


# ── Merged from profiler.py (# Profiler) ──
class FlameGraphProfiler:
    """Profiler that can output cProfile stats for flame graph generation."""

    def __init__(self, data_dir: str = ".tel"):
        self.data_dir = Path.cwd() / data_dir / "profiles"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiler: Optional[cProfile.Profile] = None
        self._active = False

    def start(self):
        """Start profiling."""
        self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._active = True

    def stop(self) -> str:
        """Stop profiling and save results. Returns path to stats file."""
        if not self._active or not self._profiler:
            return ""
        self._profiler.disable()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        stats_path = self.data_dir / f"profile_{timestamp}.stats"
        self._profiler.dump_stats(str(stats_path))

        # Also save human-readable summary
        s = io.StringIO()
        ps = pstats.Stats(self._profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(30)
        summary_path = self.data_dir / f"profile_{timestamp}.txt"
        summary_path.write_text(s.getvalue())

        self._profiler = None
        self._active = False
        return str(stats_path)

    def get_recent_profiles(self, n: int = 5) -> list:
        """List most recent profile files."""
        files = sorted(self.data_dir.glob("*.stats"), key=lambda f: f.stat().st_mtime, reverse=True)
        return [str(f) for f in files[:n]]

    @staticmethod
    def profile(func: Callable) -> Callable:
        """Decorator to profile a specific function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                return func(*args, **kwargs)
            finally:
                profiler.disable()
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                ps.print_stats(20)
                # Log to debug output
                print(f"[profile] {func.__name__}:")
                print(s.getvalue()[:500])
        return wrapper


class HotPathDetector:
    """Detects hot paths by measuring execution time of key functions."""

    def __init__(self):
        self._timings: dict = {}

    def time(self, label: str) -> callable:
        """Context manager to time a block."""
        return _Timer(self, label)

    def report(self, top_n: int = 10) -> str:
        """Generate a hot path report sorted by total time."""
        sorted_items = sorted(self._timings.items(), key=lambda x: -x[1]["total"])
        lines = ["Hot Path Report:", "-" * 60]
        lines.append(f"{'Function':<40} {'Calls':>6} {'Total (s)':>10} {'Avg (ms)':>10}")
        lines.append("-" * 60)
        for label, data in sorted_items[:top_n]:
            avg_ms = (data["total"] / data["calls"]) * 1000 if data["calls"] > 0 else 0
            lines.append(f"{label:<40} {data['calls']:>6} {data['total']:>10.3f} {avg_ms:>10.2f}")
        return "\n".join(lines)


class _Timer:
    def __init__(self, detector: HotPathDetector, label: str):
        self.detector = detector
        self.label = label
        self.start: float = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = time.perf_counter() - self.start
        if self.label not in self.detector._timings:
            self.detector._timings[self.label] = {"total": 0.0, "calls": 0}
        self.detector._timings[self.label]["total"] += elapsed
        self.detector._timings[self.label]["calls"] += 1
