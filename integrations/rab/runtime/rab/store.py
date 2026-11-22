from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATA = Path(os.environ.get("RAB_HOME", Path.home() / ".local/share/rab"))
DB = DATA / "rab.sqlite3"
MANIFEST = DATA / "capabilities.json"

_ACTION_FIELDS = {
    "transport_status", "http_status", "acknowledgement_json",
    "execution_status", "verification_status", "observed_state_json",
    "observation_requested_at", "observation_captured_at",
    "observation_received_at", "verified_at", "completed_at",
    "failure_reason", "execution_confidence", "outcome_confidence",
    "retry_count",
}


@contextmanager
def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            payload TEXT NOT NULL, created_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY, capability_id TEXT NOT NULL,
            status TEXT NOT NULL, input_json TEXT NOT NULL,
            result_json TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS objectives (
            objective_id TEXT PRIMARY KEY, goal TEXT NOT NULL,
            status TEXT NOT NULL, plan_json TEXT NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS action_records (
            action_id TEXT PRIMARY KEY,
            capability_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            request_json TEXT NOT NULL,
            expected_state TEXT,
            transport_status TEXT NOT NULL DEFAULT 'pending',
            http_status INTEGER,
            acknowledgement_json TEXT NOT NULL DEFAULT '{}',
            execution_status TEXT NOT NULL DEFAULT 'unknown',
            verification_status TEXT NOT NULL DEFAULT 'pending',
            observed_state_json TEXT,
            created_at REAL NOT NULL,
            dispatched_at REAL,
            observation_requested_at REAL,
            observation_captured_at REAL,
            observation_received_at REAL,
            verified_at REAL,
            completed_at REAL,
            failure_reason TEXT,
            execution_confidence REAL NOT NULL DEFAULT 0.0,
            outcome_confidence REAL NOT NULL DEFAULT 0.0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS action_evidence (
            evidence_id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            source TEXT NOT NULL,
            captured_at REAL,
            received_at REAL,
            supports TEXT NOT NULL,
            result TEXT NOT NULL,
            confidence REAL NOT NULL,
            payload_json TEXT NOT NULL,
            artifact_reference TEXT,
            integrity_hash TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(action_id) REFERENCES action_records(action_id)
        )""")
        db.commit()
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def emit(event_type: str, payload: dict, event_id: str | None = None) -> bool:
    import hashlib
    canonical = json.dumps([event_type, payload], sort_keys=True, separators=(",", ":"))
    key = event_id or hashlib.sha256(canonical.encode()).hexdigest()
    with connect() as db:
        cur = db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?)",
                         (key, event_type, json.dumps(payload, sort_keys=True), time.time()))
        return cur.rowcount == 1


def write_manifest(data: dict):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(MANIFEST)


def read_manifest() -> dict:
    if not MANIFEST.exists():
        return {"schema_version": 1, "capabilities": []}
    return json.loads(MANIFEST.read_text())


def create_action_record(
    action_id: str,
    capability_id: str,
    operation: str,
    request: dict,
    expected_state: str | None = None,
    dispatched_at: float | None = None,
) -> dict:
    now = time.time()
    request_json = json.dumps(request, sort_keys=True, separators=(",", ":"))
    with connect() as db:
        db.execute(
            """INSERT OR IGNORE INTO action_records
            (action_id,capability_id,operation,request_json,expected_state,
             transport_status,execution_status,verification_status,
             created_at,dispatched_at,updated_at)
            VALUES (?,?,?,?,?,'pending','unknown','pending',?,?,?)""",
            (action_id, capability_id, operation, request_json, expected_state,
             now, dispatched_at, now),
        )
        row = db.execute(
            "SELECT request_json,operation,capability_id FROM action_records WHERE action_id=?",
            (action_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Action record could not be created.")
        if row["request_json"] != request_json or row["operation"] != operation or row["capability_id"] != capability_id:
            raise ValueError("action_id is already bound to a different operation or request.")
    return get_action_record(action_id)


def update_action_record(action_id: str, **values: Any) -> None:
    unknown = set(values) - _ACTION_FIELDS
    if unknown:
        raise ValueError(f"Unsupported action record fields: {sorted(unknown)}")
    if not values:
        return
    assignments = []
    params: list[Any] = []
    for key, value in values.items():
        if key.endswith("_json") and value is not None and not isinstance(value, str):
            value = json.dumps(value, sort_keys=True)
        assignments.append(f"{key}=?")
        params.append(value)
    assignments.append("updated_at=?")
    params.extend([time.time(), action_id])
    with connect() as db:
        cur = db.execute(
            f"UPDATE action_records SET {', '.join(assignments)} WHERE action_id=?",
            params,
        )
        if cur.rowcount != 1:
            raise KeyError(f"Unknown action_id: {action_id}")


def append_action_evidence(
    action_id: str,
    evidence_type: str,
    source: str,
    supports: str,
    result: str,
    confidence: float,
    payload: dict | None = None,
    captured_at: float | None = None,
    received_at: float | None = None,
    artifact_reference: str | None = None,
    integrity_hash: str | None = None,
    evidence_id: str | None = None,
) -> str:
    if not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("confidence must be between 0 and 1.")
    key = evidence_id or str(uuid.uuid4())
    with connect() as db:
        exists = db.execute("SELECT 1 FROM action_records WHERE action_id=?", (action_id,)).fetchone()
        if not exists:
            raise KeyError(f"Unknown action_id: {action_id}")
        db.execute(
            """INSERT INTO action_evidence
            (evidence_id,action_id,evidence_type,source,captured_at,received_at,
             supports,result,confidence,payload_json,artifact_reference,integrity_hash,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, action_id, evidence_type, source, captured_at, received_at,
             supports, result, float(confidence), json.dumps(payload or {}, sort_keys=True),
             artifact_reference, integrity_hash, time.time()),
        )
    return key


def record_observation(
    action_id: str,
    observed_state: str,
    source: str,
    expected_state_match: bool | None,
    captured_at: float | None = None,
    received_at: float | None = None,
    confidence: float = 0.9,
    artifact_reference: str | None = None,
    integrity_hash: str | None = None,
) -> dict:
    record = get_action_record(action_id)
    if record is None:
        raise KeyError(f"Unknown action_id: {action_id}")
    received = received_at if received_at is not None else time.time()
    freshness = "unknown"
    if captured_at is not None and record["dispatched_at"] is not None:
        freshness = "fresh" if captured_at >= record["dispatched_at"] else "stale"

    # This API records an observation and an optional operator-supplied
    # comparison claim. It is deliberately incapable of authorizing VERIFIED.
    result = "OBSERVATION_RECORDED"
    supports = "observed_device_state"
    if freshness == "stale":
        verification_status = "stale_observation"
    elif freshness == "fresh" and expected_state_match is not None:
        verification_status = "pending"
    elif freshness == "fresh":
        verification_status = "indeterminate"
    else:
        verification_status = "indeterminate"
    verified_at = None
    outcome_confidence = 0.0

    evidence_id = append_action_evidence(
        action_id=action_id,
        evidence_type="visual_observation",
        source=source,
        captured_at=captured_at,
        received_at=received,
        supports=supports,
        result=result,
        confidence=confidence if verification_status == "verified" else 0.0,
        payload={"observed_state": observed_state, "freshness": freshness,
                 "operator_claimed_expected_state_match": expected_state_match,
                 "verification_decision": "NOT_MADE"},
        artifact_reference=artifact_reference,
        integrity_hash=integrity_hash,
    )
    update_action_record(
        action_id,
        observation_captured_at=captured_at,
        observation_received_at=received,
        observed_state_json={"state": observed_state, "source": source,
                             "freshness": freshness, "evidence_id": evidence_id},
        verification_status=verification_status,
        verified_at=verified_at,
        outcome_confidence=outcome_confidence,
    )
    return get_action_record(action_id)


def _decode_action(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["request"] = json.loads(result.pop("request_json"))
    result["acknowledgement"] = json.loads(result.pop("acknowledgement_json") or "{}")
    raw_observed = result.pop("observed_state_json")
    result["observed_state"] = json.loads(raw_observed) if raw_observed else None
    return result


def get_action_record(action_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM action_records WHERE action_id=?", (action_id,)).fetchone()
        if row is None:
            return None
        result = _decode_action(row)
        evidence = db.execute(
            "SELECT * FROM action_evidence WHERE action_id=? ORDER BY created_at,evidence_id",
            (action_id,),
        ).fetchall()
    result["evidence"] = [
        {**dict(item), "payload": json.loads(item["payload_json"])}
        for item in evidence
    ]
    return result


def list_action_records(limit: int = 20) -> list[dict]:
    if not 1 <= int(limit) <= 500:
        raise ValueError("limit must be between 1 and 500.")
    with connect() as db:
        ids = db.execute(
            "SELECT action_id FROM action_records ORDER BY created_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [record for row in ids if (record := get_action_record(row["action_id"])) is not None]
