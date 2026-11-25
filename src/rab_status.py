"""Best-effort WW -> RAB task status bridge.

WW owns agent/conversation state. RAB receives a display-oriented mirror so
its Android console can show real task progress without becoming the executor.
The bridge is deliberately loopback-only and never blocks a WW response.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from typing import Any


class RABTaskPublisher:
    def __init__(self, session: str, goal: str) -> None:
        self.base = os.getenv("WW_RAB_CONSOLE_URL", "http://127.0.0.1:8765").rstrip("/")
        self.session = session[:128]
        self.goal = goal[:500]
        self.actions: list[dict[str, Any]] = []
        self.task_id: str | None = None
        self._started = False
        self._tool_count = 0

    def _post_sync(self, path: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        request = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=1.5) as response:
            response.read(1024)

    async def _post(self, path: str, payload: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(self._post_sync, path, payload)
        except Exception:
            # Status reporting must never make the actual agent fail.
            return

    async def begin(self) -> None:
        if self._started:
            return
        self._started = True
        result = await self._post_result("/api/task/start", {
            "operation": "WW · " + self.goal[:220],
            "goal": self.goal,
            "detail": "WW conversation running; live events mirrored from the shared runtime",
            "actions": [],
        })
        if result:
            self.task_id = result.get("task_id")
        await self.event("INFO", "WW task started", self.goal)

    async def _post_result(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            data = json.dumps(payload, ensure_ascii=False).encode()
            request = urllib.request.Request(
                self.base + path, data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            def send():
                with urllib.request.urlopen(request, timeout=1.5) as response:
                    return json.loads(response.read(4096) or b"{}")
            return await asyncio.to_thread(send)
        except Exception:
            return None

    async def event(self, level: str, title: str, summary: str = "") -> None:
        await self._post("/api/event", {
            "level": level, "title": title[:200], "summary": summary[:500],
            "detail": "source=ww; session=" + self.session,
        })

    async def _sync(self, status: str, phase: str, current: str) -> None:
        await self._post("/api/state", {
            "status": status, "phase": phase[:300],
            "current_operation": current[:500],
            "ticker_text": current[:500],
            "progress": {
                "current": sum(1 for action in self.actions if action["status"] in {"completed", "failed"}),
                "total": len(self.actions),
            },
            "actions": self.actions,
        })

    async def handle(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type", ""))
        if not self._started:
            await self.begin()
        if kind == "tool_start":
            call_id = str(event.get("call_id", self._tool_count + 1))
            tool = str(event.get("tool", "tool"))
            self._tool_count += 1
            self.actions = [a for a in self.actions if a["id"] != call_id]
            self.actions.append({"id": call_id, "title": tool, "detail": "Executing in WW runtime", "status": "running"})
            await self._sync("RUNNING", "Executing tool", "WW executing " + tool)
            await self.event("ACTION", "WW tool started", tool)
        elif kind == "approval_required":
            tool = str(event.get("tool", "tool"))
            await self._sync("WAITING", "Local approval required", "Waiting for approval: " + tool)
            await self.event("WARN", "WW waiting for local approval", tool)
        elif kind == "tool_result":
            call_id = str(event.get("call_id", ""))
            output = str(event.get("output", ""))
            failed = output.startswith(("ERROR:", "DENIED:", "TOOL ERROR"))
            for action in self.actions:
                if action["id"] == call_id:
                    action["status"] = "failed" if failed else "completed"
                    action["detail"] = output[:500]
                    break
            await self._sync("RUNNING", "Reviewing tool results", "WW received result from " + str(event.get("tool", "tool")))
            await self.event("ERROR" if failed else "SUCCESS", "WW tool finished", output[:300])
        elif kind == "tool_round_complete":
            await self._sync("RUNNING", "Model reviewing tool results", "WW planning next step")
        elif kind == "execution_limit":
            await self._sync("WAITING", "Execution limit reached", str(event.get("message", "Waiting for next instruction")))
            await self.event("WARN", "WW execution limit reached", str(event.get("message", "")))
        elif kind == "done":
            await self._sync("COMPLETED", "Response complete", "WW completed the turn")
            await self.event("SUCCESS", "WW task completed", self.goal)
        elif kind == "error":
            message = str(event.get("message", "WW conversation failed"))
            await self._sync("FAILED", "Conversation failed", message)
            await self.event("ERROR", "WW task failed", message)
