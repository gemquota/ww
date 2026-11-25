import unittest
from unittest.mock import patch

from src.rab_tools import RABDeviceActionArgs, rab_device_action
from src.tools.tool_policy import ToolRisk, policy_for_tool
from src.conversation_runtime import build_tool_registry


class RABDeviceToolTests(unittest.TestCase):
    def test_registered_and_requires_local_approval(self):
        registry = build_tool_registry(".")
        self.assertIn("rab_device_action", registry.tools)
        self.assertEqual(policy_for_tool("rab_device_action").risk, ToolRisk.EXECUTION)
        self.assertTrue(policy_for_tool("rab_device_action").requires_approval)
        self.assertFalse(policy_for_tool("rab_device_action").remote_allowed)

    def test_schema_limits_operations_to_allowlist(self):
        args = RABDeviceActionArgs(operation="tap", params={"x": 12, "y": 34})
        self.assertEqual(args.operation, "tap")
        with self.assertRaises(Exception):
            RABDeviceActionArgs(operation="shell", params={"command": "id"})

    def test_device_action_requires_exact_bridge_acknowledgement(self):
        with patch("integrations.rab.runtime.rab.bridge.request", return_value={
            "accepted": True, "operation": "ping", "http_status": 200,
            "body": "RAB_PING_OK",
        }):
            self.assertIn('"accepted": true', rab_device_action("ping", {}))
        with patch("integrations.rab.runtime.rab.bridge.request", return_value={
            "accepted": False, "operation": "tap", "http_status": 503,
            "body": "unavailable",
        }):
            with self.assertRaises(RuntimeError):
                rab_device_action("tap", {"x": 1, "y": 2})


if __name__ == "__main__":
    unittest.main()
