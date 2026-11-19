import time
import unittest
import tempfile
import json
import os
from pathlib import Path

from src.tools.approvals import ApprovalLedger
from src.tools.tool_policy import ToolRisk, canonical_tool_name, policy_for_tool, remote_tool_allowed
from src.tools.local_approval import LocalApprovalController
from src.tools.audit import AuditLogError, ToolAuditLog
from src.permissions import PermissionManager


class ToolPolicyTests(unittest.TestCase):
    def test_remote_surface_is_explicitly_read_only(self):
        self.assertTrue(remote_tool_allowed("read_file"))
        self.assertTrue(remote_tool_allowed("list_dir"))
        self.assertFalse(remote_tool_allowed("read"))
        self.assertFalse(remote_tool_allowed("list"))
        for name in ("write_file", "file_patch", "git_tool", "shell_exec", "url_fetch"):
            with self.subTest(tool=name):
                self.assertFalse(remote_tool_allowed(name))

    def test_privileged_tools_require_approval(self):
        for name in ("write_file", "file_patch", "git_tool", "shell_exec", "url_fetch"):
            with self.subTest(tool=name):
                self.assertTrue(policy_for_tool(name).requires_approval)

    def test_unknown_tools_fail_closed(self):
        self.assertEqual(policy_for_tool("made_up_tool").risk, ToolRisk.DENY)
        self.assertFalse(policy_for_tool("made_up_tool").remote_allowed)
        self.assertFalse(policy_for_tool("made_up_tool").requires_approval)

    def test_registry_aliases_resolve_to_the_same_policy(self):
        self.assertEqual(canonical_tool_name("git"), "git_tool")
        self.assertTrue(policy_for_tool("git").requires_approval)
        self.assertTrue(policy_for_tool("git_tool").requires_approval)
        self.assertFalse(remote_tool_allowed("git"))


class LocalApprovalControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_audit_path = os.environ.get("WW_AUDIT_LOG")
        cls._audit_directory = tempfile.TemporaryDirectory()
        os.environ["WW_AUDIT_LOG"] = str(Path(cls._audit_directory.name) / "approval.jsonl")

    @classmethod
    def tearDownClass(cls):
        if cls._previous_audit_path is None:
            os.environ.pop("WW_AUDIT_LOG", None)
        else:
            os.environ["WW_AUDIT_LOG"] = cls._previous_audit_path
        cls._audit_directory.cleanup()

    def test_read_only_tool_does_not_prompt(self):
        controller = LocalApprovalController(
            prompt=lambda _: self.fail("read-only tools must not prompt"),
            output=lambda _: None,
        )
        self.assertTrue(controller.authorize("read_file", {"file_path": "README.md"}))


    def test_local_approval_records_request_and_decision_without_arguments(self):
        controller = LocalApprovalController(
            prompt=lambda _: "yes",
            output=lambda _: None,
            session_id="audit-test-session",
        )
        args = {"url": "https://example.com/private?token=do-not-log"}
        self.assertTrue(controller.authorize("url_fetch", args))
        audit_path = Path(os.environ["WW_AUDIT_LOG"])
        records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([record["event"] for record in records[-2:]], [
            "approval_requested", "approval_decision"
        ])
        self.assertEqual(records[-1]["decision"], "approved")
        self.assertNotIn("do-not-log", audit_path.read_text(encoding="utf-8"))


    def test_write_approval_shows_a_bounded_unified_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("before\n", encoding="utf-8")
            output = []
            controller = LocalApprovalController(
                prompt=lambda _: "yes", output=output.append,
            )
            approved = controller.authorize(
                "write_file",
                {"file_path": "notes.txt", "content": "after\n"},
                PermissionManager(root),
            )
            self.assertTrue(approved)
            rendered = "\n".join(output)
            self.assertIn("Read-only diff preview", rendered)
            self.assertIn("-before", rendered)
            self.assertIn("+after", rendered)
            self.assertIn("Exact arguments", rendered)

    def test_patch_approval_shows_the_exact_replacement_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("alpha beta\n", encoding="utf-8")
            output = []
            controller = LocalApprovalController(
                prompt=lambda _: "yes", output=output.append,
            )
            approved = controller.authorize(
                "file_patch",
                {
                    "file_path": "notes.txt",
                    "search_text": "alpha",
                    "replace_text": "omega",
                },
                PermissionManager(root),
            )
            self.assertTrue(approved)
            rendered = "\n".join(output)
            self.assertIn("-alpha beta", rendered)
            self.assertIn("+omega beta", rendered)

    def test_patch_without_a_matching_target_is_denied_before_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.txt").write_text("alpha beta\n", encoding="utf-8")
            controller = LocalApprovalController(
                prompt=lambda _: self.fail("invalid patch must not prompt"),
                output=lambda _: None,
            )
            self.assertFalse(controller.authorize(
                "file_patch",
                {
                    "file_path": "notes.txt",
                    "search_text": "missing",
                    "replace_text": "omega",
                },
                PermissionManager(root),
            ))

    def test_git_registry_alias_requires_local_approval(self):
        prompts = []
        controller = LocalApprovalController(
            prompt=lambda prompt: prompts.append(prompt) or "y",
            output=lambda _: None,
        )
        self.assertTrue(controller.authorize("git", {"command": "status"}))
        self.assertEqual(len(prompts), 1)


    def test_write_requires_explicit_local_yes_and_shows_exact_arguments(self):
        with tempfile.TemporaryDirectory() as workspace:
            previews = []
            prompts = []
            controller = LocalApprovalController(
                prompt=lambda prompt: prompts.append(prompt) or "yes",
                output=previews.append,
                session_id="local-terminal",
            )
            permission_mgr = PermissionManager(workspace)
            args = {"file_path": "README.md", "content": "approved content"}
            self.assertTrue(controller.authorize("write_file", args, permission_mgr))
            rendered = "\\n".join(previews)
            self.assertIn("approved content", rendered)
            self.assertIn("README.md", rendered)
            self.assertEqual(len(prompts), 1)

    def test_rejected_prompt_clears_pending_request(self):
        ledger = ApprovalLedger()
        with tempfile.TemporaryDirectory() as workspace:
            controller = LocalApprovalController(
                ledger=ledger,
                prompt=lambda _: "no",
                output=lambda _: None,
            )
            self.assertFalse(controller.authorize(
                "write_file",
                {"file_path": "README.md", "content": "not approved"},
                PermissionManager(workspace),
            ))
        self.assertEqual(len(ledger._pending), 0)

    def test_rejection_and_hard_deny_never_authorize(self):
        with tempfile.TemporaryDirectory() as workspace:
            controller = LocalApprovalController(
                prompt=lambda _: "no",
                output=lambda _: None,
            )
            permission_mgr = PermissionManager(workspace)
            self.assertFalse(controller.authorize(
                "write_file",
                {"file_path": "README.md", "content": "not approved"},
                permission_mgr,
            ))
            self.assertFalse(controller.authorize(
                "shell_exec",
                {"command": "rm -rf /"},
                permission_mgr,
            ))

    def test_unknown_tool_fails_closed_without_prompt(self):
        controller = LocalApprovalController(
            prompt=lambda _: self.fail("unknown tools must not prompt"),
            output=lambda _: None,
        )
        self.assertFalse(controller.authorize("unregistered_tool", {}))


    def test_protected_write_target_is_denied_before_prompt(self):
        with tempfile.TemporaryDirectory() as workspace:
            controller = LocalApprovalController(
                prompt=lambda _: self.fail("protected paths must not prompt"),
                output=lambda _: None,
            )
            permission_mgr = PermissionManager(workspace)
            self.assertFalse(controller.authorize(
                "write_file",
                {"file_path": ".env", "content": "SECRET=value"},
                permission_mgr,
            ))

    def test_eof_is_a_rejection(self):
        with tempfile.TemporaryDirectory() as workspace:
            controller = LocalApprovalController(
                prompt=lambda _: (_ for _ in ()).throw(EOFError()),
                output=lambda _: None,
            )
            self.assertFalse(controller.authorize(
                "write_file",
                {"file_path": "README.md", "content": "content"},
                PermissionManager(workspace),
            ))



    def test_audit_failure_denies_operation_before_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "protected"
            target.write_text("keep", encoding="utf-8")
            audit_path = Path(directory) / "audit.jsonl"
            audit_path.symlink_to(target)
            ledger = ApprovalLedger()
            controller = LocalApprovalController(
                ledger=ledger,
                audit_log=ToolAuditLog(audit_path),
                prompt=lambda _: self.fail("audit failure must deny before prompting"),
                output=lambda _: None,
            )
            self.assertFalse(controller.authorize(
                "url_fetch", {"url": "https://example.com"}
            ))
            self.assertEqual(len(ledger._pending), 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")


    def test_audit_failure_after_yes_still_denies_the_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            class FailOnDecisionAudit:
                def __init__(self):
                    self.inner = ToolAuditLog(Path(directory) / "audit.jsonl")
                    self.calls = 0

                def record(self, *args, **kwargs):
                    self.calls += 1
                    if self.calls == 2:
                        raise AuditLogError("simulated disk failure")
                    return self.inner.record(*args, **kwargs)

            ledger = ApprovalLedger()
            controller = LocalApprovalController(
                ledger=ledger,
                audit_log=FailOnDecisionAudit(),
                prompt=lambda _: "yes",
                output=lambda _: None,
            )
            self.assertFalse(controller.authorize(
                "url_fetch", {"url": "https://example.com"}
            ))
            self.assertEqual(len(ledger._pending), 0)
            self.assertEqual(len(ledger._grants), 0)

    def test_mutations_fail_closed_without_permission_manager(self):
        controller = LocalApprovalController(
            prompt=lambda _: self.fail("missing permission manager must deny"),
            output=lambda _: None,
        )
        self.assertFalse(controller.authorize(
            "write_file", {"file_path": "README.md", "content": "content"}
        ))
        self.assertFalse(controller.authorize(
            "shell_exec", {"command": "echo hello"}
        ))


class ToolAuditLogTests(unittest.TestCase):
    def test_records_are_redacted_and_append_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = ToolAuditLog(path)
            args = {"command": "echo private-token", "message": "secret"}
            audit.record(
                "approval_requested", tool_name="git", session_id="local-session",
                arguments=args,
            )
            audit.record(
                "approval_decision", tool_name="git", session_id="local-session",
                arguments=args, decision="approved",
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            first, second = (json.loads(line) for line in lines)
            self.assertEqual(first["tool"], "git_tool")
            self.assertEqual(second["decision"], "approved")
            self.assertEqual(first["arguments_fingerprint"], second["arguments_fingerprint"])
            self.assertNotIn("private-token", path.read_text(encoding="utf-8"))
            self.assertNotIn("secret", path.read_text(encoding="utf-8"))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_symlink_audit_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "important.txt"
            target.write_text("untouched", encoding="utf-8")
            link = Path(directory) / "audit.jsonl"
            link.symlink_to(target)
            audit = ToolAuditLog(link)
            with self.assertRaises(AuditLogError):
                audit.record(
                    "approval_requested", tool_name="shell_exec",
                    session_id="s", arguments={"command": "true"},
                )
            self.assertEqual(target.read_text(encoding="utf-8"), "untouched")



    def test_export_copies_only_to_a_new_private_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "audit.jsonl"
            audit = ToolAuditLog(source)
            audit.record(
                "approval_requested", tool_name="shell_exec", session_id="s",
                arguments={"command": "echo export"},
            )
            export_dir = root / "private-export"
            export_dir.mkdir(mode=0o700)
            destination = export_dir / "audit-copy.jsonl"
            self.assertEqual(audit.export(destination), destination)
            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(AuditLogError):
                audit.export(destination)

    def test_export_rejects_a_public_destination_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "audit.jsonl"
            audit = ToolAuditLog(source)
            audit.record(
                "approval_requested", tool_name="shell_exec", session_id="s",
                arguments={"command": "true"},
            )
            public_dir = root / "public"
            public_dir.mkdir(mode=0o755)
            public_dir.chmod(0o755)
            with self.assertRaises(AuditLogError):
                audit.export(public_dir / "audit.jsonl")

    def test_archive_preserves_history_and_starts_a_new_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            audit = ToolAuditLog(path)
            audit.record(
                "approval_requested", tool_name="shell_exec", session_id="s",
                arguments={"command": "echo one"},
            )
            archived = audit.archive()
            self.assertIsNotNone(archived)
            self.assertTrue(archived.exists())
            self.assertEqual(len(archived.read_text(encoding="utf-8").splitlines()), 1)
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "")
            self.assertEqual(archived.stat().st_mode & 0o777, 0o600)
            audit.record(
                "approval_decision", tool_name="shell_exec", session_id="s",
                arguments={"command": "echo two"}, decision="approved",
            )
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_archive_of_missing_log_is_a_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            audit = ToolAuditLog(Path(directory) / "missing.jsonl")
            self.assertIsNone(audit.archive())

    def test_full_audit_log_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            path.write_bytes(b"x" * ToolAuditLog.MAX_BYTES)
            audit = ToolAuditLog(path)
            with self.assertRaises(AuditLogError):
                audit.record(
                    "approval_requested", tool_name="shell_exec",
                    session_id="s", arguments={"command": "true"},
                )


class ApprovalLedgerTests(unittest.TestCase):
    def test_grant_is_bound_to_session_tool_and_exact_arguments(self):
        args = {"file_path": "src/example.py", "content": "safe"}
        mismatches = (
            ("other-session", "write_file", args),
            ("browser-tab-a", "shell_exec", args),
            ("browser-tab-a", "write_file", {**args, "content": "different"}),
        )
        for session_id, tool_name, supplied_args in mismatches:
            with self.subTest(session=session_id, tool=tool_name, args=supplied_args):
                ledger = ApprovalLedger()
                request = ledger.request(
                    session_id="browser-tab-a",
                    tool_name="write_file",
                    arguments=args,
                )
                token = ledger.approve(request.request_id)
                self.assertFalse(ledger.consume(
                    token,
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=supplied_args,
                ))

    def test_rejected_request_is_removed_and_cannot_be_approved(self):
        ledger = ApprovalLedger()
        request = ledger.request(
            session_id="local-session",
            tool_name="write_file",
            arguments={"file_path": "README.md", "content": "x"},
        )
        self.assertTrue(ledger.reject(request.request_id))
        self.assertFalse(ledger.reject(request.request_id))
        with self.assertRaises(ValueError):
            ledger.approve(request.request_id)

    def test_valid_grant_is_single_use(self):
        ledger = ApprovalLedger()
        args = {"command": "pytest"}
        request = ledger.request(
            session_id="local-session",
            tool_name="shell_exec",
            arguments=args,
        )
        token = ledger.approve(request.request_id)
        self.assertTrue(ledger.consume(
            token, session_id="local-session", tool_name="shell_exec", arguments=args
        ))
        self.assertFalse(ledger.consume(
            token, session_id="local-session", tool_name="shell_exec", arguments=args
        ))

    def test_read_only_or_unknown_tools_cannot_request_privileged_grants(self):
        ledger = ApprovalLedger()
        for name in ("read_file", "made_up_tool"):
            with self.subTest(tool=name):
                with self.assertRaises(ValueError):
                    ledger.request(session_id="s", tool_name=name, arguments={})

    def test_pending_and_grant_stores_are_bounded(self):
        ledger = ApprovalLedger(max_pending=1, max_grants=1)
        first = ledger.request(
            session_id="s", tool_name="write_file", arguments={"file_path": "a"}
        )
        with self.assertRaises(RuntimeError):
            ledger.request(
                session_id="s", tool_name="write_file", arguments={"file_path": "b"}
            )
        token = ledger.approve(first.request_id)
        second = ledger.request(
            session_id="s", tool_name="write_file", arguments={"file_path": "b"}
        )
        with self.assertRaises(RuntimeError):
            ledger.approve(second.request_id)
        self.assertTrue(ledger.consume(
            token, session_id="s", tool_name="write_file", arguments={"file_path": "a"}
        ))
        self.assertIsNotNone(ledger.approve(second.request_id))

    def test_pending_request_and_grant_expire(self):
        ledger = ApprovalLedger(request_ttl=0.01, grant_ttl=0.01)
        pending = ledger.request(
            session_id="s", tool_name="write_file", arguments={"file_path": "a"}
        )
        time.sleep(0.02)
        with self.assertRaises(ValueError):
            ledger.approve(pending.request_id)

        pending = ledger.request(
            session_id="s", tool_name="write_file", arguments={"file_path": "b"}
        )
        token = ledger.approve(pending.request_id)
        time.sleep(0.02)
        self.assertFalse(ledger.consume(
            token, session_id="s", tool_name="write_file", arguments={"file_path": "b"}
        ))


if __name__ == "__main__":
    unittest.main()
