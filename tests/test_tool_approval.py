import time
import unittest

from src.tools.approvals import ApprovalLedger
from src.tools.tool_policy import ToolRisk, policy_for_tool, remote_tool_allowed


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
