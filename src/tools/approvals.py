"""One-time, argument-bound approval grants for privileged tool operations.

The ledger is intentionally in-memory and is not exposed as an HTTP endpoint.
Restarting WW invalidates every outstanding request and grant (fail closed).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

from src.tools.tool_policy import policy_for_tool


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    tool_name: str
    expires_at: float


def _arguments_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(
        arguments,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ApprovalLedger:
    """Issue and consume short-lived grants scoped to one exact operation."""

    def __init__(self, *, request_ttl: float = 300.0, grant_ttl: float = 120.0):
        if request_ttl <= 0 or grant_ttl <= 0:
            raise ValueError("approval lifetimes must be positive")
        self.request_ttl = request_ttl
        self.grant_ttl = grant_ttl
        self._pending: dict[str, dict[str, Any]] = {}
        self._grants: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        self._pending = {
            key: value for key, value in self._pending.items()
            if value["expires_at"] > now
        }
        self._grants = {
            key: value for key, value in self._grants.items()
            if value["expires_at"] > now
        }

    def request(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ApprovalRequest:
        """Create a pending request for a known tool that requires approval."""
        policy = policy_for_tool(tool_name)
        if not policy.requires_approval:
            raise ValueError(f"Tool '{tool_name}' does not require an approval grant")
        if not session_id or len(session_id) > 128:
            raise ValueError("session_id must contain 1 to 128 characters")

        now = time.monotonic()
        request_id = secrets.token_urlsafe(18)
        expires_at = now + self.request_ttl
        record = {
            "session_id": session_id,
            "tool_name": tool_name,
            "arguments_digest": _arguments_digest(arguments),
            "expires_at": expires_at,
        }
        with self._lock:
            self._prune(now)
            self._pending[request_id] = record
        return ApprovalRequest(request_id, tool_name, expires_at)

    def approve(self, request_id: str) -> str:
        """Approve a pending request from a trusted local control surface."""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            record = self._pending.pop(request_id, None)
            if record is None:
                raise ValueError("Approval request is missing, expired, or already decided")
            token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            self._grants[token_hash] = {
                **record,
                "expires_at": now + self.grant_ttl,
            }
            return token

    def consume(
        self,
        token: str,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        """Consume a grant once, only for its original session/tool/arguments."""
        if not token:
            return False
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = time.monotonic()
        digest = _arguments_digest(arguments)
        with self._lock:
            self._prune(now)
            record = self._grants.pop(token_hash, None)
            if record is None:
                return False
            session_matches = hmac.compare_digest(record["session_id"], session_id)
            tool_matches = hmac.compare_digest(record["tool_name"], tool_name)
            args_match = hmac.compare_digest(record["arguments_digest"], digest)
            return session_matches and tool_matches and args_match
