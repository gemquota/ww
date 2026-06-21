"""
Causal Event Graph — parent/child event linking with SQLite persistence.

Extends the DecisionTracer with causal chains: every event records its
parent(s), enabling full ancestry tracing for the /why command.

Addresses: Causal observability, branch enforcement, post-hoc debugging.
"""

from __future__ import annotations

import json
import time
import uuid
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Callable


class CausalDivergenceError(Exception):
    """Raised when a causal branch is missing or invalid."""
    pass


@dataclass
class CausalEvent:
    """A single node in the causal event graph."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    event_type: str = "default"
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    session_id: str = ""
    agent_id: str = ""
    tool_name: str = ""
    summary: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CausalEvent":
        return cls(**d)


class CausalGraph:
    """Persistent causal event graph with SQLite backend.

    Usage:
        cg = CausalGraph(db_path=Path(".tel/causal.db"))
        root = cg.create_event("task_start", summary="Implement feature X")
        child = cg.create_event("tool_call", parent_ids=[root.event_id],
                                 tool_name="read_file")
        cg.link(parent=root, child=child)
        lineage = cg.trace(root.event_id)  # full ancestry chain
    """

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or Path(".tel/causal.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS causal_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                parent_ids TEXT DEFAULT '[]',
                child_ids TEXT DEFAULT '[]',
                session_id TEXT DEFAULT '',
                agent_id TEXT DEFAULT '',
                tool_name TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                data TEXT DEFAULT '{}',
                timestamp REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_causal_parents
                ON causal_events(event_id);
            CREATE INDEX IF NOT EXISTS idx_causal_type
                ON causal_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_causal_session
                ON causal_events(session_id);
            CREATE INDEX IF NOT EXISTS idx_causal_tool
                ON causal_events(tool_name);
        """)
        conn.commit()

    def create_event(
        self,
        event_type: str,
        *,
        parent_ids: Optional[List[str]] = None,
        session_id: str = "",
        agent_id: str = "",
        tool_name: str = "",
        summary: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> CausalEvent:
        """Create and persist a new causal event."""
        event = CausalEvent(
            event_type=event_type,
            parent_ids=parent_ids or [],
            session_id=session_id,
            agent_id=agent_id,
            tool_name=tool_name,
            summary=summary,
            data=data or {},
        )
        self._persist(event)
        return event

    def _persist(self, event: CausalEvent) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO causal_events
               (event_id, event_type, parent_ids, child_ids,
                session_id, agent_id, tool_name, summary, data, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.event_type,
                json.dumps(event.parent_ids),
                json.dumps(event.child_ids),
                event.session_id,
                event.agent_id,
                event.tool_name,
                event.summary,
                json.dumps(event.data),
                event.timestamp,
            ),
        )
        conn.commit()

    def link(self, parent: CausalEvent, child: CausalEvent) -> None:
        """Link parent -> child in the causal graph (bidirectional)."""
        conn = self._get_conn()
        # Add child to parent's child_ids
        parent_data = self.get_event(parent.event_id)
        if parent_data and child.event_id not in json.loads(parent_data["child_ids"]):
            p_child_ids = json.loads(parent_data["child_ids"])
            p_child_ids.append(child.event_id)
            conn.execute(
                "UPDATE causal_events SET child_ids=? WHERE event_id=?",
                (json.dumps(p_child_ids), parent.event_id),
            )
        # Add parent to child's parent_ids
        if parent.event_id not in child.parent_ids:
            child.parent_ids.append(parent.event_id)
            conn.execute(
                "UPDATE causal_events SET parent_ids=? WHERE event_id=?",
                (json.dumps(child.parent_ids), child.event_id),
            )
        conn.commit()

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single event by ID."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM causal_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def trace(self, event_id: str, max_depth: int = 20) -> List[Dict[str, Any]]:
        """Walk the causal chain upward (parents) from an event.

        Returns ordered list from oldest ancestor to the event itself.
        """
        chain: List[Dict[str, Any]] = []
        visited: Set[str] = set()
        current_id = event_id
        guard = 0

        while current_id and current_id not in visited and guard < max_depth:
            visited.add(current_id)
            event = self.get_event(current_id)
            if event is None:
                break
            chain.append(event)
            # Walk to the first parent (primary causal link)
            parents = json.loads(event["parent_ids"])
            current_id = parents[0] if parents else None
            guard += 1

        chain.reverse()
        return chain

    def trace_children(
        self, event_id: str, max_depth: int = 20
    ) -> List[Dict[str, Any]]:
        """Walk the causal chain downward (children) from an event."""
        results: List[Dict[str, Any]] = []
        event = self.get_event(event_id)
        if event is None:
            return results
        results.append(event)
        child_ids = json.loads(event["child_ids"])
        guard = 0
        stack = list(child_ids)
        while stack and guard < max_depth:
            cid = stack.pop()
            child = self.get_event(cid)
            if child:
                results.append(child)
                grandchildren = json.loads(child["child_ids"])
                stack.extend(grandchildren)
            guard += 1
        return results

    def get_session_events(
        self, session_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get all events for a session, ordered by timestamp."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM causal_events
               WHERE session_id=? ORDER BY timestamp ASC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tool_chain(
        self, tool_name: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent events for a specific tool."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM causal_events
               WHERE tool_name=? ORDER BY timestamp DESC LIMIT ?""",
            (tool_name, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
