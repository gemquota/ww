"""Two-system UI decision controller with local experience memory.

System One (Jev) proposes an action. System Two is supplied by the host agent
as a deliberation callback. This module deliberately does not execute UI input.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.ui_decision import JevConfigurationError, JevRequestError, decide_ui_action, jev_enabled

DEFAULT_DB = Path(os.getenv(
    "WW_UI_CONTROLLER_DB",
    str(Path(os.getenv("WW_DATA_DIR", str(Path.home() / ".local/share/ww"))) / "ui_controller.sqlite3"),
)).expanduser()


def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective TEXT NOT NULL,
            state_key TEXT NOT NULL,
            action_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS episodes_state ON episodes(state_key, created_at)")
    conn.commit()
    return conn


def state_key(observation: dict[str, Any]) -> str:
    """Stable, privacy-conscious key from coarse UI state only."""
    fields = ("app", "screen", "page", "dialog", "mode")
    normalized = {k: observation[k] for k in fields if k in observation}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def experience_summary(observation: dict[str, Any], candidates: list[dict[str, str]], db_path: Path = DEFAULT_DB) -> dict:
    key = state_key(observation)
    conn = _db(db_path)
    try:
        rows = conn.execute(
            "SELECT action_id,outcome,COUNT(*) AS n,MAX(created_at) AS last_seen "
            "FROM episodes WHERE state_key=? GROUP BY action_id,outcome ORDER BY n DESC",
            (key,),
        ).fetchall()
    finally:
        conn.close()
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        counts.setdefault(row["action_id"], {})[row["outcome"]] = row["n"]
    allowed = {c["id"] for c in candidates}
    return {
        "state_key": key,
        "known": {action: values for action, values in counts.items() if action in allowed},
        "total_observations": sum(sum(v.values()) for v in counts.values()),
    }


def record_feedback(
    *, objective: str, observation: dict[str, Any], action_id: str,
    outcome: str, note: str = "", db_path: Path = DEFAULT_DB,
) -> dict:
    if outcome not in {"success", "failure", "uncertain"}:
        raise ValueError("outcome must be success, failure or uncertain")
    if not action_id or len(action_id) > 64:
        raise ValueError("action_id is invalid")
    # Store coarse state and short operator note only. Do not persist raw screenshots
    # or page text; callers should redact personal data before supplying notes.
    conn = _db(db_path)
    try:
        conn.execute(
            "INSERT INTO episodes(objective,state_key,action_id,outcome,note,created_at) VALUES(?,?,?,?,?,?)",
            (objective[:1000], state_key(observation), action_id, outcome, note[:500], time.time()),
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    finally:
        conn.close()
    return {"recorded": True, "outcome": outcome, "experience_count": count}


async def decide(
    *,
    objective: str,
    observation: dict[str, Any],
    candidates: list[dict[str, str]],
    system2: Callable[[str, dict[str, Any], list[dict[str, str]], dict], Awaitable[dict]] | None = None,
    db_path: Path = DEFAULT_DB,
) -> dict:
    """Route decision to Jev (S1) or host deliberation (S2), fail safely."""
    memory = experience_summary(observation, candidates, db_path)
    s1: dict | None = None
    if jev_enabled():
        try:
            s1 = await decide_ui_action(objective=objective, observation=observation, candidates=candidates)
        except (JevConfigurationError, JevRequestError, ValueError) as exc:
            s1 = {"status": "escalate", "reasons": [f"system-one-unavailable:{type(exc).__name__}"]}
    else:
        s1 = {"status": "escalate", "reasons": ["system-one-disabled"]}

    # Experience may inform S2 but never bypass confidence/risk controls.
    if s1.get("status") == "suggest":
        history = memory["known"].get(s1["action_id"], {})
        successes = history.get("success", 0)
        failures = history.get("failure", 0)
        # Repeated failures override a fast suggestion; a success streak is
        # surfaced to the planner, not used as a permission grant.
        if failures >= 2 and failures > successes:
            s1["status"] = "escalate"
            s1.setdefault("reasons", []).append("negative-experience")
    if s1.get("status") == "suggest":
        return {
            "system": "S1",
            "status": "suggest",
            "suggestion": s1,
            "experience": memory,
            "execution_permitted": False,
        }
    if system2 is None:
        return {
            "system": "S2",
            "status": "needs-deliberation",
            "system1": s1,
            "experience": memory,
            "execution_permitted": False,
        }
    try:
        result = await system2(objective, observation, candidates, memory)
    except Exception as exc:
        return {
            "system": "S2",
            "status": "deliberation-unavailable",
            "system1": s1,
            "experience": memory,
            "reason": f"system-two-error:{type(exc).__name__}",
            "execution_permitted": False,
        }
    selected = result.get("action_id") if isinstance(result, dict) else None
    if selected not in {c["id"] for c in candidates}:
        return {
            "system": "S2",
            "status": "invalid-deliberation-result",
            "system1": s1,
            "experience": memory,
            "execution_permitted": False,
        }
    return {
        "system": "S2",
        "status": "suggest",
        "suggestion": result,
        "system1": s1,
        "experience": memory,
        "execution_permitted": False,
    }
