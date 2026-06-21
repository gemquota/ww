"""
Multi-tier memory system with SQLite persistence.
Port from 2b/harness — adapted for Gemini Web API context management.

Three-tier memory:
- Tier A (Hot): Recent verbatim history
- Tier B (Compressed): Key facts and state changes
- Tier C (Archival): Dense narrative summaries
"""

import sqlite3
import tracemalloc
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field


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


class MemoryEvent(BaseModel):
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_usage: Optional[str] = None
    importance: float = 0.5
    metadata: Dict[str, Any] = {}
    row_id: Optional[int] = None  # SQLite rowid for safe deletion


class SessionDatabase:
    """SQLite-based session persistence."""

    def __init__(self, db_path: Optional[str] = None, batch_size: int = 10):
        if db_path is None:
            db_dir = Path.cwd() / ".ww" / "sessions"
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(db_dir / "sessions.db")
        else:
            self.db_path = db_path
        self._batch_size = batch_size
        self._event_buffer: list = []
        self._init_db()

    def _enable_wal(self):
        """Enable WAL mode for better concurrent read/write performance.
        WAL mode persists across connections once set.
        """
        try:
            with _get_db_connection(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass  # WAL is a perf optimization; non-critical

    def _init_db(self):
        """Initialize database with WAL mode and necessary tables."""
        self._enable_wal()
        with _get_db_connection(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    created_at TIMESTAMP,
                    last_active TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    session_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP,
                    tool_usage TEXT,
                    importance REAL,
                    metadata TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scratchpad (
                    session_id INTEGER,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY(session_id, key),
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    event_id INTEGER,
                    label TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    source_id INTEGER,
                    target_id INTEGER,
                    type TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            # Performance indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_session_ts ON history(session_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_session_role ON history(session_id, role)")

    def get_or_create_session(self, name: str) -> int:
        now = datetime.now().isoformat()
        with _get_db_connection(self.db_path) as conn:
            cursor = conn.execute("SELECT id FROM sessions WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                conn.execute("UPDATE sessions SET last_active = ? WHERE id = ?", (now, row[0]))
                return row[0]
            else:
                cursor = conn.execute(
                    "INSERT INTO sessions (name, created_at, last_active) VALUES (?, ?, ?)",
                    (name, now, now)
                )
                return cursor.lastrowid

    def save_event(self, session_id: int, event: MemoryEvent):
        """Queue an event for batch write. Call flush_events() to persist."""
        self._event_buffer.append((session_id, event))
        if len(self._event_buffer) >= self._batch_size:
            self.flush_events()

    def flush_events(self) -> int:
        """Flush all buffered events to SQLite in a single transaction.
        Returns the number of events flushed."""
        if not self._event_buffer:
            return 0
        count = len(self._event_buffer)
        with _get_db_connection(self.db_path) as conn:
            conn.execute("BEGIN")
            for session_id, event in self._event_buffer:
                conn.execute(
                    "INSERT INTO history (session_id, role, content, timestamp, tool_usage, importance, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, event.role, event.content, event.timestamp, event.tool_usage, event.importance, json.dumps(event.metadata))
                )
            _crash_safe_commit(conn)
        self._event_buffer.clear()
        return count

    def flush_all(self) -> int:
        """Flush all buffers (events + scratchpad). Convenience for shutdown."""
        return self.flush_events()

    def load_events(self, session_id: int) -> List[MemoryEvent]:
        # Flush buffered writes first so reads see all data
        self.flush_events()
        with _get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT rowid, role, content, timestamp, tool_usage, importance, metadata FROM history WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            return [
                MemoryEvent(
                    row_id=row[0], role=row[1], content=row[2], timestamp=row[3],
                    tool_usage=row[4], importance=row[5], metadata=json.loads(row[6])
                ) for row in cursor.fetchall()
            ]

    def update_scratchpad(self, session_id: int, key: str, value: Any):
        """Write scratchpad value immediately (low-volume, not batched)."""
        with _get_db_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO scratchpad (session_id, key, value) VALUES (?, ?, ?)",
                (session_id, key, json.dumps(value) if not isinstance(value, str) else value)
            )
            _crash_safe_commit(conn)

    def get_scratchpad(self, session_id: int) -> Dict[str, Any]:
        with _get_db_connection(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT key, value FROM scratchpad WHERE session_id = ?", (session_id,)
            )
            result = {}
            for key, value in cursor.fetchall():
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
            return result

    def clear_history(self, session_id: int):
        self.flush_events()
        with _get_db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE session_id = ?", (session_id,))


class MemoryGraph:
    """Persistent Cognitive Graph (PCG) for tracking causal relationships."""

    def __init__(self, db: SessionDatabase, session_id: int):
        self.db = db
        self.session_id = session_id

    def add_node(self, event_id: int, label: str) -> int:
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO graph_nodes (session_id, event_id, label) VALUES (?, ?, ?)",
                (self.session_id, event_id, label)
            )
            return cursor.lastrowid

    def add_edge(self, source_id: int, target_id: int, edge_type: str):
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute(
                "INSERT INTO graph_edges (session_id, source_id, target_id, type) VALUES (?, ?, ?, ?)",
                (self.session_id, source_id, target_id, edge_type)
            )

    def get_causal_chain(self, node_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT n.label, e.type, n2.label
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.source_id
                JOIN graph_nodes n2 ON e.target_id = n2.id
                WHERE n.id = ? OR n2.id = ?
            """, (node_id, node_id))
            return [{"source": row[0], "type": row[1], "target": row[2]} for row in cursor.fetchall()]


def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """Get a SQLite connection with production PRAGMA settings."""
    conn = sqlite3.connect(db_path, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA wal_autocheckpoint=1000")
    return conn


class MemoryManager:
    """Manages conversation memory with tiered context and SQLite persistence."""

    def __init__(self, session_name: str = "default"):
        self.db = SessionDatabase()
        self.session_id = self.db.get_or_create_session(session_name)
        self.graph = MemoryGraph(self.db, self.session_id)
        self._tier_a_limit = 20
        # In-memory cache for hot path: avoids SQLite reads on every build_context
        self._event_cache: list = []
        self._cache_dirty: bool = False  # max recent events in verbatim form

    def score_event(self, event: MemoryEvent) -> float:
        score = 0.5
        if event.tool_usage:
            score += 0.2
        if "error" in event.content.lower() or "failed" in event.content.lower():
            score += 0.4
        if event.role == "user":
            score += 0.1
        if len(event.content) > 500:
            score += 0.1
        return min(score, 1.0)

    def add_event(self, event: MemoryEvent) -> None:
        event.importance = self.score_event(event)
        self.db.save_event(self.session_id, event)  # adds to batch buffer
        # Update in-memory cache (immediate, no DB read needed)
        self._event_cache.append(event)
        self._cache_dirty = True

    def add_turn(self, role: str, content: str, tool_usage: Optional[str] = None) -> None:
        event = MemoryEvent(role=role, content=content, tool_usage=tool_usage)
        self.add_event(event)

    def get_history(self) -> List[MemoryEvent]:
        # Use in-memory cache if available and not stale
        if self._event_cache and self._cache_dirty:
            self._event_cache = self.db.load_events(self.session_id)
            self._cache_dirty = False
        elif self._event_cache and not self._cache_dirty:
            return self._event_cache
        else:
            self._event_cache = self.db.load_events(self.session_id)
        return self._event_cache

    def build_context(self, max_tier_a: int = 20) -> List[Dict[str, str]]:
        """
        Build a tiered context list for injection into the system prompt.

        Returns a list of dicts with 'role' and 'content' keys.
        Tier A = most recent events (verbatim)
        Tier B = compressed scratchpad facts
        Tier C = summary from scratchpad if available
        PCG = causal chains from MemoryGraph
        """
        events = self.get_history()
        context = []

        # Tier C: scratchpad summary
        scratchpad = self.db.get_scratchpad(self.session_id)
        if scratchpad:
            facts = scratchpad.get("compressed_facts", [])
            if facts:
                context.append({
                    "role": "system",
                    "content": f"KEY FACTS:\n- " + "\n- ".join(facts if isinstance(facts, list) else [str(facts)])
                })

        # PCG: causal chains from last N tool-using events
        tool_events = [e for e in events if e.tool_usage][-5:]
        if tool_events:
            chains = []
            for i, ev in enumerate(tool_events):
                # Try to find graph nodes for this event
                chain = self.graph.get_causal_chain(i + 1)
                if chain:
                    for link in chain:
                        chains.append(f"  {link.get('source', '?')} --[{link.get('type', '?')}]--> {link.get('target', '?')}")
            if chains:
                context.append({
                    "role": "system",
                    "content": "CAUSAL CHAINS (PCG):\n" + "\n".join(chains)
                })

        # Tier A: recent events
        tier_a = events[-max_tier_a:]
        for e in tier_a:
            context.append({"role": e.role, "content": e.content})

        return context

    def update_scratchpad(self, key: str, value: Any):
        self.db.update_scratchpad(self.session_id, key, value)

    def compress_tier_a(self, max_verbatim: int = 20) -> int:
        """
        Compress older Tier A events into Tier B (compressed facts).

        When event count exceeds max_verbatim, older events are summarized
        into scratchpad facts and removed from the hot tier.
        Returns number of compressed events.
        """
        events = self.db.load_events(self.session_id)
        if len(events) <= max_verbatim:
            return 0

        # Events to compress (oldest ones)
        compress_count = len(events) - max_verbatim
        to_compress = events[:compress_count]
        remaining = events[compress_count:]

        # Extract key facts from compressed events
        existing_facts = self.db.get_scratchpad(self.session_id).get("compressed_facts", [])
        if not isinstance(existing_facts, list):
            existing_facts = []

        new_facts = []
        for ev in to_compress:
            content = ev.content.strip()
            if not content:
                continue
            if ev.role == "assistant" and len(content) > 50:
                # Truncate and store as fact
                fact = f"[{ev.role}] {content[:200]}"
                if fact not in existing_facts and fact not in new_facts:
                    new_facts.append(fact)
            elif ev.tool_usage:
                fact = f"[tool:{ev.tool_usage}] {content[:150]}"
                if fact not in existing_facts and fact not in new_facts:
                    new_facts.append(fact)

        # Merge with existing facts (keep newest 50)
        merged = (new_facts + existing_facts)[:50]
        self.db.update_scratchpad(self.session_id, "compressed_facts", merged)

        # Remove compressed events from DB using rowid (safe deletion)
        with sqlite3.connect(self.db.db_path) as conn:
            for ev in to_compress:
                if ev.row_id is not None:
                    conn.execute(
                        "DELETE FROM history WHERE rowid = ? AND session_id = ?",
                        (ev.row_id, self.session_id)
                    )
                else:
                    conn.execute(
                        "DELETE FROM history WHERE session_id = ? AND timestamp = ? AND role = ? AND content = ?",
                        (self.session_id, ev.timestamp, ev.role, ev.content)
                    )

        return compress_count

    def compress_tier_b(self, max_facts: int = 30) -> int:
        """
        Compress Tier B (scratchpad facts) into Tier C (narrative summary).

        When the number of compressed facts exceeds max_facts, they are
        condensed into a dense narrative summary stored under
        'narrative_summary' in the scratchpad. This prevents unbounded
        fact accumulation in Tier B.

        Returns the number of facts compressed.
        """
        scratchpad = self.db.get_scratchpad(self.session_id)
        facts = scratchpad.get("compressed_facts", [])
        if not isinstance(facts, list):
            facts = []
        if len(facts) <= max_facts:
            return 0

        # Older facts to compress
        compress_count = len(facts) - max_facts
        to_compress = facts[:compress_count]
        remaining = facts[compress_count:]

        # Build narrative summary from compressed facts
        summary_lines = []
        for fact in to_compress:
            if fact.startswith("[assistant]") or fact.startswith("[tool:"):
                summary_lines.append(fact)

        # Merge with existing narrative summary
        existing_summary = scratchpad.get("narrative_summary", "")
        if existing_summary:
            summary_lines.insert(0, f"[CONTINUED FROM PREVIOUS SUMMARY] {existing_summary[:300]}")

        new_summary = "\n".join(summary_lines) if summary_lines else ""

        # Update scratchpad
        if new_summary:
            self.db.update_scratchpad(self.session_id, "narrative_summary", new_summary)
        self.db.update_scratchpad(self.session_id, "compressed_facts", remaining)

        return compress_count

    def flush(self):
        """Flush buffered events to SQLite and sync cache.
        
        Forces any pending batched writes to be committed to SQLite.
        Call before session end to ensure data persistence.
        """
        self.db.flush_all()
        if self._cache_dirty:
            self._event_cache = self.db.load_events(self.session_id)
            self._cache_dirty = False

    async def periodic_flush(self, interval: float = 5.0):
        """Periodically flush batched writes to SQLite.
        
        Runs in a background asyncio task to ensure buffered events
        are persisted even if the batch threshold isn't reached.
        Call with asyncio.create_task(memory.periodic_flush(5.0)).
        """
        import asyncio
        while True:
            try:
                await asyncio.sleep(interval)
                if self.db._event_buffer:
                    flushed = self.db.flush_all()
                    if flushed and self._cache_dirty:
                        self._event_cache = self.db.load_events(self.session_id)
                        self._cache_dirty = False
            except asyncio.CancelledError:
                # Flush one last time on cancellation
                self.flush()
                raise
            except Exception:
                pass  # Don't crash the loop on transient errors

    def clear_history(self):
        self.db.clear_history(self.session_id)

    def get_scratchpad_summary(self) -> str:
        data = self.db.get_scratchpad(self.session_id)
        if not data:
            return "Scratchpad: Empty."
        return "SCRATCHPAD STATE:\n" + json.dumps(data, indent=2)


class CorruptionDetector:
    """Detect database corruption at startup — NEW-V5-D3#4 (Dr. Helena Bergstrom)."""

    @staticmethod
    def check_database(db_path: str) -> dict:
        """Run integrity checks on a SQLite database.
        
        Returns dict with: corrupt (bool), issues (list), tables (int).
        """
        import sqlite3
        from pathlib import Path
        
        result = {"path": db_path, "corrupt": False, "issues": [], "tables": 0}
        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            result["issues"].append("Database file not found")
            return result
        if db_path_obj.stat().st_size == 0:
            result["issues"].append("Database file is empty (0 bytes)")
            result["corrupt"] = True
            return result
        try:
            conn = sqlite3.connect(str(db_path_obj))
            cursor = conn.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            if integrity_result != "ok":
                result["issues"].append(f"Integrity check failed: {integrity_result}")
                result["corrupt"] = True
            cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            result["tables"] = cursor.fetchone()[0]
            cursor = conn.execute("PRAGMA page_count")
            result["pages"] = cursor.fetchone()[0]
            conn.close()
        except sqlite3.DatabaseError as e:
            result["issues"].append(f"Database error: {e}")
            result["corrupt"] = True
        except Exception as e:
            result["issues"].append(f"Unexpected error: {e}")
            result["corrupt"] = True
        return result

    @staticmethod
    def check_all_databases() -> dict:
        """Check all known databases for corruption."""
        from pathlib import Path
        results = {}
        for db_path in [Path(".tel/telemetry.db"), Path(".tel/sessions/sessions.db"), Path("events.db")]:
            if db_path.exists():
                results[str(db_path)] = CorruptionDetector.check_database(str(db_path))
        return results


class CrossSessionRecovery:
    """Cross-session recovery path — NEW-V5-D3#3 (Dr. Helena Bergstrom).
    Enables recovering a session from backup when primary is corrupt.
    """

    def __init__(self, memory_manager):
        self.mm = memory_manager

    def recover_from_backup(self, session_id: str, backup_dir: str = ".backups") -> bool:
        """Attempt to recover a session from backup."""
        from pathlib import Path
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return False
        # Try to find backup for this session
        for candidate in sorted(backup_path.glob(f"*{session_id}*")):
            try:
                import shutil
                shutil.copy(candidate, Path(self.mm.db_path) if hasattr(self.mm, 'db_path') else Path(".tel/sessions/sessions.db"))
                return True
            except Exception:
                continue
        return False
