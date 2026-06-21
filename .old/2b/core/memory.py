import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

from pydantic import BaseModel, Field

class MemoryEvent(BaseModel):
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    tool_usage: Optional[str] = None
    importance: float = 0.5
    metadata: Dict[str, Any] = {}

class StructuredEvent(BaseModel):
    intent: str
    entities: List[str]
    tools: List[str]
    importance_hint: float

class SessionDatabase:
    """
    SQLite-based session persistence for the Gemma 2B agent.
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Workspace-specific memory: use .sessions in the CURRENT directory
            db_dir = Path.cwd() / ".sessions"
            db_dir.mkdir(exist_ok=True)
            self.db_path = str(db_dir / "sessions.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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

    def get_or_create_session(self, name: str) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
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
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO history (session_id, role, content, timestamp, tool_usage, importance, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, event.role, event.content, event.timestamp, event.tool_usage, event.importance, json.dumps(event.metadata))
            )

    def load_events(self, session_id: int) -> List[MemoryEvent]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT role, content, timestamp, tool_usage, importance, metadata FROM history WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,)
            )
            return [
                MemoryEvent(
                    role=row[0],
                    content=row[1],
                    timestamp=row[2],
                    tool_usage=row[3],
                    importance=row[4],
                    metadata=json.loads(row[5])
                ) for row in cursor.fetchall()
            ]

    def update_scratchpad(self, session_id: int, key: str, value: Any):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO scratchpad (session_id, key, value) VALUES (?, ?, ?)",
                (session_id, key, json.dumps(value))
            )

    def get_scratchpad(self, session_id: int) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT key, value FROM scratchpad WHERE session_id = ?", (session_id,))
            return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

    def clear_history(self, session_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM history WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM scratchpad WHERE session_id = ?", (session_id,))

class ContextController:
    """
    Manages context window with Multi-tier Memory Strata:
    Tier A: Hot Context (Recent turns verbatim)
    Tier B: Compressed Facts (High-signal facts/state)
    Tier C: Archival Summary (Lossy narrative summary)
    """
    def __init__(self, max_tokens: int = 8192):
        self.max_tokens = max_tokens
        self.hot_threshold = 10 # Last 10 turns are "Hot"
        self.compression_threshold = 0.7 # 70% of max_tokens
        self.is_compressed = False

    async def process_history(self, history: List[MemoryEvent], agent: Any, memory_manager: Any, use_web: bool = False) -> List[Dict[str, str]]:
        """
        Applies multi-tier strata if thresholds are met.
        """
        total_chars = sum(len(h.content) for h in history)
        est_tokens = total_chars // 4
        
        if est_tokens < self.max_tokens * self.compression_threshold:
            return [{"role": h.role, "content": h.content} for h in history]

        source = "Gemini Web" if use_web else "Local 2B"
        print(f"\n[Memory Manager]: Context pressure high. Transitioning to Multi-tier Strata using {source}...")
        
        # Tier A: Hot Context (Last N turns)
        tier_a_events = history[-self.hot_threshold:]
        older_events = history[:-self.hot_threshold]
        
        # Check if we already have a summary and facts in scratchpad
        scratchpad = memory_manager.db.get_scratchpad(memory_manager.session_id)
        current_summary = scratchpad.get("archival_summary", "")
        current_facts = scratchpad.get("compressed_facts", [])

        if older_events:
            text_to_process = "\n".join([f"{h.role}: {h.content}" for h in older_events])
            
            new_facts = []
            new_summary = ""

            if use_web:
                # Use Gemini Web for high-quality extraction/summarization
                from utils.web_client import get_web_client
                web_client = await get_web_client()
                if web_client:
                    # Extract Facts
                    fact_prompt = f"Extract a bulleted list of key facts and state changes from this conversation:\n\n{text_to_process}"
                    fact_resp = await web_client.ask(fact_prompt)
                    if fact_resp:
                        new_facts = [f.strip("- ").strip() for f in fact_resp.splitlines() if f.strip()]
                    
                    # Archival Summary
                    sum_prompt = f"Update this archival summary with the following new events. Keep it dense.\n\nSUMMARY: {current_summary}\n\nNEW EVENTS: {text_to_process}"
                    new_summary = await web_client.ask(sum_prompt) or current_summary
                else:
                    # Fallback to local if web fails
                    new_facts = agent.extract_facts(text_to_process)
                    combined_text = f"PREVIOUS SUMMARY: {current_summary}\n\nNEW EVENTS:\n{text_to_process}"
                    new_summary = agent.summarize(combined_text)
            else:
                # Local 2B
                new_facts = agent.extract_facts(text_to_process)
                combined_text = f"PREVIOUS SUMMARY: {current_summary}\n\nNEW EVENTS:\n{text_to_process}"
                new_summary = agent.summarize(combined_text)
            
            updated_facts = list(set(current_facts + new_facts))
            memory_manager.db.update_scratchpad(memory_manager.session_id, "compressed_facts", updated_facts)
            memory_manager.db.update_scratchpad(memory_manager.session_id, "archival_summary", new_summary)
            
            current_summary = new_summary
            current_facts = updated_facts

        # Construct final context
        context = []
        if current_summary:
            context.append({"role": "system", "content": f"ARCHIVAL SUMMARY:\n{current_summary}"})
        if current_facts:
            facts_str = "- " + "\n- ".join(current_facts)
            context.append({"role": "system", "content": f"KEY FACTS & STATE:\n{facts_str}"})
        for h in tier_a_events:
            context.append({"role": h.role, "content": h.content})
            
        return context

class MemoryManager:
    def __init__(self, session_name: str = "default", use_web_memory: bool = False):
        self.db = SessionDatabase()
        self.session_id = self.db.get_or_create_session(session_name)
        self.controller = ContextController()
        self.use_web_memory = use_web_memory
        self.graph = MemoryGraph(self.db, self.session_id)

    def score_event(self, event: MemoryEvent) -> float:
        """Heuristic importance scoring for memory events."""
        score = 0.5 # Baseline

        if event.tool_usage:
            score += 0.2

        if "error" in event.content.lower() or "failed" in event.content.lower():
            score += 0.4

        if event.role == "user":
            score += 0.1

        if len(event.content) > 500:
            score += 0.1

        return min(score, 1.0)

    def add_event(self, event: MemoryEvent) -> int:
        event.importance = self.score_event(event)
        return self.db.save_event(self.session_id, event)

    def add_turn(self, role: str, content: str, tool_usage: Optional[str] = None) -> int:
        event = MemoryEvent(role=role, content=content, tool_usage=tool_usage)
        return self.add_event(event)

    def get_history(self) -> List[MemoryEvent]:
        return self.db.load_events(self.session_id)

    async def process_history(self, agent: Any) -> List[Dict[str, str]]:
        """Processes and compresses history into context tiers."""
        history = self.get_history()
        return await self.controller.process_history(history, agent, self, use_web=self.use_web_memory)

    def update_scratchpad(self, key: str, value: Any):
        self.db.update_scratchpad(self.session_id, key, value)

    def clear_history(self):
        self.db.clear_history(self.session_id)
        self.controller.is_summarized = False

    def get_scratchpad_summary(self) -> str:
        data = self.db.get_scratchpad(self.session_id)
        if not data:
            return "Scratchpad: Empty."
        return "SCRATCHPAD STATE:\n" + json.dumps(data, indent=2)

    def mask_observation(self, output: str, max_lines: int = 15) -> str:
        lines = str(output).splitlines()
        if len(lines) <= max_lines:
            return str(output)
        return f"[Truncated Output: {len(lines)} lines]\n" + "\n".join(lines[:max_lines]) + "\n..."

class MemoryGraph:
    """
    Persistent Cognitive Graph (PCG) for tracking causal relationships.
    """
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
        """Retrieves nodes connected by 'caused_by' or 'result_of' edges."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT n.label, e.type, n2.label 
                FROM graph_nodes n
                JOIN graph_edges e ON n.id = e.source_id
                JOIN graph_nodes n2 ON e.target_id = n2.id
                WHERE n.id = ? OR n2.id = ?
            """, (node_id, node_id))
            return [{"source": row[0], "type": row[1], "target": row[2]} for row in cursor.fetchall()]
