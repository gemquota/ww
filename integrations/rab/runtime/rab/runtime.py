from __future__ import annotations

import json
import subprocess
import time
import uuid

from .store import (
    read_manifest, connect, emit, create_action_record,
    update_action_record, get_action_record,
)
from . import bridge


class CapabilityError(RuntimeError):
    pass


def _capability(cid):
    cap = next((c for c in read_manifest()["capabilities"] if c["id"] == cid), None)
    if not cap or cap["state"] not in ("executable", "verified"):
        raise CapabilityError(f"Capability is not executable: {cid}")
    return cap


def execute(
    cid: str,
    inputs: dict,
    operation_id: str | None = None,
    expected_state: str | None = None,
):
    cap = _capability(cid)
    execution_id = operation_id or str(uuid.uuid4())
    canonical_inputs = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    with connect() as db:
        old = db.execute(
            "SELECT status,result_json,input_json FROM executions WHERE execution_id=?",
            (execution_id,),
        ).fetchone()
        if old:
            if old["input_json"] != canonical_inputs:
                raise ValueError("operation_id is already bound to a different request.")
            old_status = old["status"]
            return {
                "execution_id": execution_id,
                "status": "indeterminate" if old_status == "running" else old_status,
                "result": json.loads(old["result_json"]),
                "replayed": True,
                "recovery_required": old_status == "running",
            }
        db.execute(
            "INSERT INTO executions VALUES (?,?,?,?,?,?,?)",
            (execution_id, cid, "running", canonical_inputs, "{}", time.time(), None),
        )

    action_record_created = False
    is_bridge = cid == "automation.rab_android_bridge"
    if is_bridge:
        operation = inputs.get("operation")
        params = {k: v for k, v in inputs.items() if k != "operation"}
        dispatched_at = time.time()
        create_action_record(
            action_id=execution_id,
            capability_id=cid,
            operation=str(operation),
            request=params,
            expected_state=expected_state,
            dispatched_at=dispatched_at,
        )
        action_record_created = True
        append_dispatch = {
            "action_id": execution_id,
            "capability_id": cid,
            "operation": operation,
            "dispatched_at": dispatched_at,
        }
        from .store import append_action_evidence
        append_action_evidence(
            action_id=execution_id,
            evidence_type="dispatch",
            source="RAB",
            supports="request_dispatched",
            result="DISPATCHED",
            confidence=0.0,
            payload=append_dispatch,
            captured_at=dispatched_at,
            received_at=dispatched_at,
        )

    try:
        if is_bridge:
            operation = inputs.get("operation")
            params = {k: v for k, v in inputs.items() if k != "operation"}
            result = bridge.request(operation, params)
            acknowledged_at = time.time()
            if result["accepted"]:
                status = "acknowledged"
                transport_status = "acknowledged"
                failure_reason = None
            else:
                status = "indeterminate"
                transport_status = "rejected"
                failure_reason = result.get("body") or f"HTTP {result.get('http_status')}"
            update_action_record(
                execution_id,
                transport_status=transport_status,
                http_status=result.get("http_status"),
                acknowledgement_json=result,
                execution_status="unknown",
                verification_status="pending",
                execution_confidence=0.1 if result["accepted"] else 0.0,
                failure_reason=failure_reason,
            )
            from .store import append_action_evidence
            append_action_evidence(
                action_id=execution_id,
                evidence_type="bridge_acknowledgement",
                source="MacroDroid-HTTP",
                supports="bridge_response_received",
                result="ACKNOWLEDGED" if result["accepted"] else "REJECTED_OR_UNEXPECTED",
                confidence=0.1 if result["accepted"] else 0.0,
                payload={"http_status": result.get("http_status"),
                         "body": result.get("body"),
                         "accepted": result.get("accepted")},
                captured_at=acknowledged_at,
                received_at=acknowledged_at,
            )
            result = {
                **result,
                "action_id": execution_id,
                "execution_status": "unknown",
                "verification_status": "pending",
                "note": "Bridge acknowledgement is not proof of input execution or the expected UI outcome.",
            }
        elif cid in ("android.notification", "android.toast"):
            binary = cap["details"]["path"]
            if cid == "android.notification":
                title, content = inputs.get("title", "RAB"), inputs.get("content", "")
                if not content:
                    raise ValueError("content is required")
                args = [binary, "--title", str(title), "--content", str(content),
                        "--id", str(inputs.get("notification_id", "rab-status"))]
            else:
                message = inputs.get("message", "")
                if not message:
                    raise ValueError("message is required")
                args = [binary, message]
            p = subprocess.run(args, capture_output=True, text=True, timeout=5)
            result = {"exit_code": p.returncode, "stdout": p.stdout.strip(),
                      "stderr": p.stderr.strip(), "adapter": "local_process"}
            status = "accepted" if p.returncode == 0 else "failed"
        else:
            raise CapabilityError(f"No safe execution adapter is registered for {cid}")
    except Exception as e:
        if is_bridge and action_record_created:
            status = "indeterminate"
            result = {"error": str(e), "ambiguous": True,
                      "note": "The request may have reached MacroDroid; do not retry with a new action ID until the device state is reconciled."}
            update_action_record(
                execution_id,
                transport_status="unknown",
                execution_status="unknown",
                verification_status="pending",
                failure_reason=str(e),
            )
            from .store import append_action_evidence
            append_action_evidence(
                action_id=execution_id,
                evidence_type="transport_error",
                source="RAB",
                supports="transport_outcome",
                result="UNKNOWN",
                confidence=0.0,
                payload={"error": str(e), "ambiguous": True},
                received_at=time.time(),
            )
        else:
            result, status = {"error": str(e)}, "failed"

    with connect() as db:
        db.execute(
            "UPDATE executions SET status=?,result_json=?,finished_at=? WHERE execution_id=?",
            (status, json.dumps(result), time.time(), execution_id),
        )
    emit("CAPABILITY_EXECUTION_FINISHED", {
        "execution_id": execution_id, "capability_id": cid, "status": status
    }, event_id="execution:" + execution_id)
    return {
        "execution_id": execution_id,
        "status": status,
        "result": result,
        "replayed": False,
        "action_record": get_action_record(execution_id) if is_bridge else None,
    }
