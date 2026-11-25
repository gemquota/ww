"""WW tool adapter for explicitly approved RAB Android operations."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class RABDeviceActionArgs(BaseModel):
    operation: Literal[
        "ping", "screenshot", "tap", "drag", "type",
        "launch_app", "notify", "stream", "clear",
    ] = Field(description="Allowlisted RAB/MacroDroid operation.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific fields. tap: x,y; drag: start_x,start_y,end_x,end_y,duration_ms; type: text; launch_app: package; notify: title,message; stream: message; ping/screenshot/clear: empty.",
    )


def rab_device_action(operation: str, params: dict[str, Any] | None = None) -> str:
    """Execute one allowlisted device operation through RAB's verified bridge."""
    from integrations.rab.runtime.rab.bridge import request

    result = request(operation, params or {})
    if not result.get("accepted"):
        raise RuntimeError(
            f"RAB operation {operation!r} was not accepted "
            f"(HTTP {result.get('http_status')}): {result.get('body', 'no acknowledgement')}"
        )
    return json.dumps({
        "accepted": True,
        "operation": operation,
        "http_status": result["http_status"],
        "acknowledgement": result["body"],
    }, ensure_ascii=False)
