"""Jev-backed decision support for UI controllers.

Jev proposes structured judgments; this module never performs UI actions.
The caller remains responsible for permissions, execution and verification.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
MAX_STATE_BYTES = 16_384
MAX_ACTIONS = 16


class JevConfigurationError(RuntimeError):
    """Jev is not configured or its request is invalid."""


class JevRequestError(RuntimeError):
    """The Jev API could not provide a usable decision."""


def jev_enabled() -> bool:
    """Return whether the hosted decision service is configured."""
    return bool(os.getenv("TYPESAFE_API_KEY", "").strip())


def _request(payload: dict[str, Any], api_key: str, timeout: float) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ww-jev-ui-controller/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JevRequestError(f"Jev returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise JevRequestError(f"Jev request failed: {type(exc).__name__}.") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JevRequestError("Jev returned an invalid JSON response.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise JevRequestError("Jev response did not contain an answers map.")
    return result


def _answer_value(answer: Any, key: str) -> Any:
    return answer.get(key) if isinstance(answer, dict) else None


async def decide_ui_action(
    *,
    objective: str,
    observation: dict[str, Any],
    candidates: list[dict[str, str]],
    timeout: float | None = None,
) -> dict[str, Any]:
    """Ask Jev to select a UI action and identify cases needing deliberation.

    Candidate entries require id, description and risk (low, medium or high).
    The returned action is advisory and is never executed.
    """
    api_key = os.getenv("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise JevConfigurationError("TYPESAFE_API_KEY is not configured.")
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("objective must not be empty")
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    if not candidates or len(candidates) > MAX_ACTIONS:
        raise ValueError(f"candidates must contain 1 to {MAX_ACTIONS} actions")

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be an object")
        action_id = str(candidate.get("id", "")).strip()
        description = str(candidate.get("description", "")).strip()
        risk = str(candidate.get("risk", "medium")).strip().lower()
        if not action_id or len(action_id) > 64 or action_id in seen:
            raise ValueError("candidate ids must be unique non-empty strings up to 64 characters")
        if not description or len(description) > 500:
            raise ValueError("candidate descriptions must contain 1 to 500 characters")
        if risk not in {"low", "medium", "high"}:
            raise ValueError("candidate risk must be low, medium or high")
        seen.add(action_id)
        normalized.append({"id": action_id, "description": description, "risk": risk})

    state = {
        "objective": objective[:1000],
        "ui_observation": observation,
        "candidate_actions": normalized,
    }
    state_text = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    if len(state_text.encode("utf-8")) > MAX_STATE_BYTES:
        raise ValueError(f"UI state exceeds {MAX_STATE_BYTES} bytes")

    criteria = {item["id"]: item["description"] for item in normalized}
    payload = {
        "model": os.getenv("WW_JEV_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        "state": state_text,
        "questions": {
            "next_action": {
                "type": "choice",
                "instructions": "Which single candidate action best advances the objective from the observed UI state? Choose only an available candidate. Prefer reversible, minimal actions.",
                "criteria": criteria,
            },
            "needs_deliberation": {
                "type": "noul",
                "instructions": "Does this UI situation require slower deliberate reasoning before any action is taken, because the state is ambiguous, unfamiliar, contradictory, or the consequences are unclear?",
            },
        },
    }
    request_timeout = timeout if timeout is not None else float(os.getenv("WW_JEV_TIMEOUT", "8"))
    response = await asyncio.to_thread(_request, payload, api_key, request_timeout)
    answers = response["answers"]
    action_answer = answers.get("next_action", {})
    deliberation_answer = answers.get("needs_deliberation", {})
    selected = _answer_value(action_answer, "choice")
    probabilities = _answer_value(action_answer, "probabilities")
    confidence = _answer_value(action_answer, "confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        confidence_value = 0.0
    try:
        deliberation_probability = float(_answer_value(deliberation_answer, "noul") or 0.0)
    except (TypeError, ValueError):
        deliberation_probability = 1.0
    if not math.isfinite(confidence_value):
        confidence_value = 0.0
    if not math.isfinite(deliberation_probability):
        deliberation_probability = 1.0
    confidence_value = min(1.0, max(0.0, confidence_value))
    deliberation_probability = min(1.0, max(0.0, deliberation_probability))

    selected_candidate = next((item for item in normalized if item["id"] == selected), None)
    if selected_candidate is None:
        raise JevRequestError("Jev selected an action outside the supplied candidate set.")

    reasons: list[str] = []
    if confidence_value < float(os.getenv("WW_JEV_MIN_CONFIDENCE", "0.75")):
        reasons.append("low-confidence")
    if deliberation_probability >= float(os.getenv("WW_JEV_DELIBERATION_THRESHOLD", "0.35")):
        reasons.append("deliberation-requested")
    if selected_candidate["risk"] != "low":
        reasons.append(f'{selected_candidate["risk"]}-risk-action')

    return {
        "status": "escalate" if reasons else "suggest",
        "action_id": selected_candidate["id"],
        "confidence": confidence_value,
        "probabilities": probabilities if isinstance(probabilities, dict) else {},
        "deliberation_probability": deliberation_probability,
        "reasons": reasons,
        "model": response.get("model"),
        "usage": response.get("usage", {}),
        "execution_permitted": False,
    }
