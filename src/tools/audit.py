"""Redacted, append-only audit records for privileged WW tool operations."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.tools.tool_policy import canonical_tool_name


class AuditLogError(RuntimeError):
    """Raised when an audit event cannot be durably recorded."""


class ToolAuditLog:
    """Write bounded JSONL audit events without storing arguments or secrets.

    The log is local to the WW user, mode 0600, append-only, and capped at
    1 MiB. Reaching the cap or failing to write is an error, allowing callers
    to fail closed instead of performing an unaudited privileged operation.
    """

    MAX_BYTES = 1024 * 1024
    EVENTS = {
        "approval_requested",
        "approval_decision",
        "execution_finished",
        "execution_interrupted",
    }
    DECISIONS = {"approved", "rejected", "denied"}
    OUTCOMES = {"success", "error", "timeout", "cancelled", "unknown"}

    def __init__(self, path: str | Path | None = None):
        configured = os.environ.get("WW_AUDIT_LOG")
        self.path = Path(path or configured or "~/.ww/audit/audit.jsonl").expanduser().absolute()
        self._lock = threading.Lock()

    @staticmethod
    def _digest(value: Any) -> str:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def record(
        self,
        event: str,
        *,
        tool_name: str,
        session_id: str,
        arguments: dict[str, Any],
        decision: str | None = None,
        outcome: str | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        """Durably append one redacted event and return its safe representation."""
        if event not in self.EVENTS:
            raise ValueError("Unsupported audit event")
        if decision is not None and decision not in self.DECISIONS:
            raise ValueError("Unsupported audit decision")
        if outcome is not None and outcome not in self.OUTCOMES:
            raise ValueError("Unsupported audit outcome")
        if not isinstance(arguments, dict) or not session_id:
            raise ValueError("Audit requires an argument object and session")
        if duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0):
            raise ValueError("duration_ms must be a non-negative integer")

        event_record = {
            "schema": 1,
            "event_id": secrets.token_hex(12),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "tool": canonical_tool_name(tool_name),
            "session": self._digest(session_id)[:16],
            "arguments_sha256": self._digest(arguments),
            "decision": decision,
            "outcome": outcome,
            "duration_ms": duration_ms,
        }
        line = (json.dumps(event_record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

        with self._lock:
            try:
                parent = self.path.parent
                parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if parent.is_symlink():
                    raise AuditLogError("Audit directory must not be a symlink")
                if parent.stat().st_mode & 0o077:
                    raise AuditLogError("Audit directory permissions must be 0700")

                flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
                flags |= getattr(os, "O_NOFOLLOW", 0)
                fd = os.open(self.path, flags, 0o600)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise AuditLogError("Audit target must be a single-link regular file")
                    os.fchmod(fd, 0o600)
                    if info.st_size + len(line) > self.MAX_BYTES:
                        raise AuditLogError("Audit log reached its 1 MiB limit")
                    written = 0
                    while written < len(line):
                        written += os.write(fd, line[written:])
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except AuditLogError:
                raise
            except OSError as exc:
                raise AuditLogError(f"Unable to write audit record: {exc}") from exc
        return event_record
