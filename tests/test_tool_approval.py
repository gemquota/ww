import time
import unittest
import tempfile
from pathlib import Path

from src.tools.approvals import ApprovalLedger
from src.tools.tool_policy import ToolRisk, canonical_tool_name, policy_for_tool, remote_tool_allowed
from src.tools.local_approval import LocalApprovalController
from src.permissions import PermissionManager


class ToolPolicyTests(unittest.TestCase):
    def test_remote_surface_is_explicitly_read_only(self):
        self.assertTrue(remote_tool_allowed("read_file"))
        self.assertTrue(remote_tool_allowed("list_dir"))
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
    def test_read_only_tool_does_not_prompt(self):
        controller = LocalApprovalController(
            prompt=lambda _: self.fail("read-only tools must not prompt"),
            output=lambda _: None,
        )
        self.assertTrue(controller.authorize("read_file", {"file_path": "README.md"}))

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
