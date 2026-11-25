"""Approved WW -> RAB UI action orchestration.

This tool is itself execution-risk and requires WW's local approval before
entry. Jev/Gemini choose only among fixed, validated candidates. The RAB
runtime records transport evidence; it does not claim visual verification.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from src.ui_controller import decide as decide_ui
from src.ui_deliberation import deliberate_ui_action

AllowedOperation = Literal["tap", "drag", "type", "launch_app"]


class RABUICandidate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=300)
    operation: AllowedOperation
    params: dict[str, Any] = Field(default_factory=dict)
    risk: Literal["low", "medium", "high"] = "low"

    @field_validator("params")
    @classmethod
    def validate_params(cls, value: dict[str, Any], info):
        operation = info.data.get("operation")
        if operation is None:
            return value
        from integrations.rab.runtime.rab.bridge import _validate
        return _validate(operation, value)


class RABUIActionArgs(BaseModel):
    objective: str = Field(min_length=1, max_length=1000)
    observation: dict[str, Any] = Field(default_factory=dict)
    candidates: list[RABUICandidate] = Field(min_length=1, max_length=12)

    @field_validator("candidates")
    @classmethod
    def unique_ids_and_risk(cls, value):
        ids = [candidate.id for candidate in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate IDs must be unique.")
        if any(candidate.risk == "high" for candidate in value):
            raise ValueError("High-risk actions require a separate explicit action flow and are not executable through this controller.")
        return value


async def rab_ui_action(
    objective: str,
    observation: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> str:
    """Decide, dispatch once through RAB, and return pending verification state."""
    normalized = [RABUICandidate.model_validate(item).model_dump() for item in candidates]
    decision_candidates = [
        {"id": item["id"], "description": item["description"], "risk": item["risk"]}
        for item in normalized
    ]
    decision = await decide_ui(
        objective=objective,
        observation=observation,
        candidates=decision_candidates,
        system2=deliberate_ui_action,
    )
    if decision.get("status") != "suggest":
        return str({
            "status": decision.get("status", "blocked"),
            "decision": decision,
            "execution_permitted": False,
        })
    selected_id = decision.get("suggestion", {}).get("action_id")
    selected = next((item for item in normalized if item["id"] == selected_id), None)
    if selected is None:
        return str({"status": "invalid-selection", "execution_permitted": False})

    operation_id = "ww-ui-" + uuid.uuid4().hex
    from integrations.rab.runtime.rab.runtime import execute
    inputs = {"operation": selected["operation"], **selected["params"]}
    result = await asyncio.to_thread(
        execute, "automation.rab_android_bridge", inputs, operation_id
    )
    action_record = result.get("action_record") or {}
    if result.get("status") not in {"acknowledged"}:
        # Ambiguous transport outcomes are never retried automatically.
        return str({
            "status": "indeterminate",
            "decision": decision,
            "rab": result,
            "retry_permitted": False,
            "verification_status": action_record.get("verification_status", "pending"),
            "execution_permitted": False,
        })
    return str({
        "status": "dispatched",
        "decision": decision,
        "selected_candidate": selected_id,
        "rab": result,
        "verification_status": action_record.get("verification_status", "pending"),
        "note": "MacroDroid acknowledged the request. This is not proof that Android executed it or reached the expected UI state.",
        "execution_permitted": False,
    })
