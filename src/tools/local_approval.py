"""Device-local human approval for privileged WW tool calls.

This controller is used by the interactive terminal executor only. It is not
registered as a model tool and has no HTTP approval endpoint.
"""
from __future__ import annotations

import difflib
import json
import secrets
from typing import Any, Callable

from src.permissions import PermissionLevel
from src.tools.approvals import ApprovalLedger
from src.tools.audit import AuditLogError, ToolAuditLog
from src.tools.tool_policy import ToolRisk, canonical_tool_name, policy_for_tool


class LocalApprovalController:
    """Require an interactive terminal decision before privileged operations."""

    def __init__(
        self,
        *,
        ledger: ApprovalLedger | None = None,
        audit_log: ToolAuditLog | None = None,
        prompt: Callable[[str], str] | None = None,
        output: Callable[[str], None] | None = None,
        session_id: str | None = None,
    ):
        self.ledger = ledger or ApprovalLedger()
        self.audit_log = audit_log or ToolAuditLog()
        self.prompt = prompt or input
        self.output = output or print
        self.session_id = session_id or secrets.token_urlsafe(18)

    def _record(self, event: str, tool_name: str, arguments: dict[str, Any], **fields: Any) -> bool:
        try:
            self.audit_log.record(
                event,
                tool_name=tool_name,
                session_id=self.session_id,
                arguments=arguments,
                **fields,
            )
            return True
        except (AuditLogError, TypeError, ValueError):
            self.output("DENIED: The audit log could not record this operation.")
            return False


    DIFF_PREVIEW_MAX_BYTES = 256 * 1024
    DIFF_PREVIEW_MAX_LINES = 80
    DIFF_PREVIEW_MAX_CHARS = 10000

    def _show_file_diff(self, tool_name: str, arguments: dict[str, Any], permission_mgr: Any) -> bool:
        """Show a bounded, read-only diff before asking for write approval."""
        if tool_name not in {"write_file", "file_patch"}:
            return True
        try:
            file_path = arguments["file_path"]
            target = permission_mgr.sandbox.resolve(file_path)
            if target.exists() and not target.is_file():
                self.output("DENIED: The write target is not a regular file.")
                return False

            old_content = ""
            if target.exists():
                if target.stat().st_size > self.DIFF_PREVIEW_MAX_BYTES:
                    if tool_name == "file_patch":
                        self.output("DENIED: file_patch target exceeds the safe diff-preview limit.")
                        return False
                    if not isinstance(arguments.get("content"), str):
                        self.output("DENIED: write_file content must be text.")
                        return False
                    self.output("│ Diff preview omitted: existing file exceeds 256 KiB.")
                    return True
                old_content = target.read_text(encoding="utf-8", errors="replace")

            if tool_name == "write_file":
                new_content = arguments.get("content")
                if not isinstance(new_content, str):
                    self.output("DENIED: write_file content must be text.")
                    return False
            else:
                search_text = arguments.get("search_text")
                replace_text = arguments.get("replace_text")
                if not isinstance(search_text, str) or not search_text:
                    self.output("DENIED: file_patch requires non-empty search_text.")
                    return False
                if not isinstance(replace_text, str):
                    self.output("DENIED: file_patch replace_text must be text.")
                    return False
                if not target.exists() or search_text not in old_content:
                    self.output("DENIED: file_patch search_text does not match the target file.")
                    return False
                new_content = old_content.replace(search_text, replace_text, 1)

            if len(new_content.encode("utf-8")) > self.DIFF_PREVIEW_MAX_BYTES:
                self.output("│ Diff preview omitted: replacement content exceeds 256 KiB.")
                return True

            diff_lines = list(difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            ))
            self.output("│ Read-only diff preview:")
            if not diff_lines:
                self.output("│ (no textual changes)")
                return True

            shown = 0
            chars = 0
            for line in diff_lines:
                rendered = line.rstrip("\n")
                if shown >= self.DIFF_PREVIEW_MAX_LINES or chars + len(rendered) > self.DIFF_PREVIEW_MAX_CHARS:
                    self.output("│ [... diff preview truncated ...]")
                    break
                self.output(f"│ {rendered}")
                shown += 1
                chars += len(rendered)
            return True
        except (KeyError, OSError, UnicodeError, ValueError) as exc:
            self.output(f"DENIED: Unable to preview the write target ({exc}).")
            return False

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
            if isinstance(arguments, dict):
                self._record("approval_decision", canonical_name, arguments, decision="denied")
            return False
        if not policy.requires_approval:
            return True

        if not isinstance(arguments, dict):
            self.output("DENIED: Tool arguments must be a JSON object.")
            return False

        if canonical_name in {"write_file", "file_patch", "shell_exec"} and permission_mgr is None:
            self.output("DENIED: The local permission manager is unavailable.")
            self._record("approval_decision", canonical_name, arguments, decision="denied")
            return False

        request_id = None
        try:
            if permission_mgr is not None:
                if canonical_name in {"write_file", "file_patch"}:
                    file_path = arguments.get("file_path")
                    if not isinstance(file_path, str) or not file_path:
                        self.output("DENIED: A valid file_path is required for this operation.")
                        self._record("approval_decision", canonical_name, arguments, decision="denied")
                        return False
                    if permission_mgr.classify_write(file_path) is PermissionLevel.DENY:
                        self.output(f"DENIED: The target path is protected: {file_path}")
                        self._record("approval_decision", canonical_name, arguments, decision="denied")
                        return False
                    if not self._show_file_diff(canonical_name, arguments, permission_mgr):
                        self._record("approval_decision", canonical_name, arguments, decision="denied")
                        return False
                elif canonical_name == "shell_exec":
                    command = arguments.get("command")
                    if not isinstance(command, str) or not command:
                        self.output("DENIED: A non-empty command is required.")
                        self._record("approval_decision", canonical_name, arguments, decision="denied")
                        return False
                    if permission_mgr.classify_command(command) is PermissionLevel.DENY:
                        self.output("DENIED: The command matches a hard-deny rule.")
                        self._record("approval_decision", canonical_name, arguments, decision="denied")
                        return False

            request = self.ledger.request(
                session_id=self.session_id,
                tool_name=canonical_name,
                arguments=arguments,
            )
            request_id = request.request_id
            if not self._record("approval_requested", canonical_name, arguments):
                self.ledger.reject(request_id)
                return False

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
                self.ledger.reject(request_id)
                self._record("approval_decision", canonical_name, arguments, decision="rejected")
                return False

            grant = self.ledger.approve(request.request_id)
            consumed = self.ledger.consume(
                grant,
                session_id=self.session_id,
                tool_name=canonical_name,
                arguments=arguments,
            )
            if not consumed:
                self._record("approval_decision", canonical_name, arguments, decision="denied")
                return False
            return self._record(
                "approval_decision", canonical_name, arguments, decision="approved"
            )
        except (EOFError, KeyboardInterrupt):
            if request_id:
                self.ledger.reject(request_id)
            self._record("approval_decision", canonical_name, arguments, decision="rejected")
            self.output("DENIED: No local approval decision was received.")
            return False
        except Exception as exc:
            if request_id:
                self.ledger.reject(request_id)
            self._record("approval_decision", canonical_name, arguments, decision="denied")
            self.output(f"DENIED: Approval could not be completed ({exc}).")
            return False
