"""Device-local human approval for privileged WW tool calls.

This controller is used by the interactive terminal executor only. It is not
registered as a model tool and has no HTTP approval endpoint.
"""
from __future__ import annotations

import json
import secrets
from typing import Any, Callable

from src.permissions import PermissionLevel
from src.tools.approvals import ApprovalLedger
from src.tools.tool_policy import ToolRisk, canonical_tool_name, policy_for_tool


class LocalApprovalController:
    """Require an interactive terminal decision before privileged operations."""

    def __init__(
        self,
        *,
        ledger: ApprovalLedger | None = None,
        prompt: Callable[[str], str] | None = None,
        output: Callable[[str], None] | None = None,
        session_id: str | None = None,
    ):
        self.ledger = ledger or ApprovalLedger()
        self.prompt = prompt or input
        self.output = output or print
        self.session_id = session_id or secrets.token_urlsafe(18)

    def authorize(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        permission_mgr: Any | None = None,
    ) -> bool:
        """Return true only for read-only tools or a locally approved exact call."""
        canonical_name = canonical_tool_name(tool_name)
        policy = policy_for_tool(canonical_name)
        if policy.risk is ToolRisk.DENY:
            self.output(f"DENIED: No execution policy exists for tool '{tool_name}'.")
            return False
        if not policy.requires_approval:
            return True

        if not isinstance(arguments, dict):
            self.output("DENIED: Tool arguments must be a JSON object.")
            return False

        # Retain the existing hard-deny path checks, but do not rely on its
        # softer on-request/always prompt policy as the approval mechanism.
        try:
            if permission_mgr is not None:
                if canonical_name in {"write_file", "file_patch"}:
                    file_path = arguments.get("file_path")
                    if not isinstance(file_path, str) or not file_path:
                        self.output("DENIED: A valid file_path is required for this operation.")
                        return False
                    if permission_mgr.classify_write(file_path) is PermissionLevel.DENY:
                        self.output(f"DENIED: The target path is protected: {file_path}")
                        return False
                elif canonical_name == "shell_exec":
                    command = arguments.get("command")
                    if not isinstance(command, str) or not command:
                        self.output("DENIED: A non-empty command is required.")
                        return False
                    if permission_mgr.classify_command(command) is PermissionLevel.DENY:
                        self.output("DENIED: The command matches a hard-deny rule.")
                        return False

            request = self.ledger.request(
                session_id=self.session_id,
                tool_name=canonical_name,
                arguments=arguments,
            )
            preview = json.dumps(
                arguments,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            self.output("")
            self.output("╭─ WW TOOL APPROVAL REQUEST ─────────────────────────")
            self.output(f"│ Tool: {canonical_name}")
            self.output(f"│ Request: {request.request_id}")
            self.output("│ Exact arguments:")
            for line in preview.splitlines():
                self.output(f"│ {line}")
            self.output("╰───────────────────────────────────────────────────")
            decision = self.prompt("Approve this exact operation? [y/N] ").strip().lower()
            if decision not in {"y", "yes"}:
                return False

            grant = self.ledger.approve(request.request_id)
            return self.ledger.consume(
                grant,
                session_id=self.session_id,
                tool_name=canonical_name,
                arguments=arguments,
            )
        except (EOFError, KeyboardInterrupt):
            self.output("DENIED: No local approval decision was received.")
            return False
        except Exception as exc:
            self.output(f"DENIED: Approval could not be completed ({exc}).")
            return False
