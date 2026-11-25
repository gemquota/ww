import json
import unittest
from unittest.mock import AsyncMock, patch

from src.rab_ui_controller import RABUICandidate, rab_ui_action


class RABUIControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.candidate = {
            "id": "tap-settings",
            "description": "Open settings",
            "operation": "tap",
            "params": {"x": 100, "y": 200},
            "risk": "low",
            "expected_state": "Settings screen is visible",
        }
        self.decision = {
            "system": "S1",
            "status": "suggest",
            "suggestion": {"action_id": "tap-settings"},
            "execution_permitted": False,
        }

    def test_candidate_schema_uses_bridge_allowlist(self):
        parsed = RABUICandidate.model_validate(self.candidate)
        self.assertEqual(parsed.params, {"x": 100, "y": 200})
        with self.assertRaises(Exception):
            RABUICandidate.model_validate({
                **self.candidate, "operation": "shell", "params": {"command": "id"}
            })
        with self.assertRaises(Exception):
            RABUICandidate.model_validate({
                **self.candidate, "params": {"x": -1, "y": 200}
            })

    async def test_decision_dispatches_once_and_keeps_verification_pending(self):
        acknowledged = {
            "status": "acknowledged",
            "action_record": {"verification_status": "pending"},
            "result": {"body": "RAB_TAP_OK"},
        }
        with patch("integrations.rab.runtime.rab.store.read_manifest", return_value={"capabilities":[{"id":"automation.rab_android_bridge","state":"executable"}]}), \
             patch("integrations.rab.runtime.rab.bridge.probe", return_value={"reachable": True}), \
             patch("src.rab_ui_controller.decide_ui", new=AsyncMock(return_value=self.decision)), \
             patch("integrations.rab.runtime.rab.runtime.execute", return_value=acknowledged) as execute:
            raw = await rab_ui_action(
                "Open settings", {"app": "demo", "screen": "home"}, [self.candidate]
            )
        result = json.loads(raw)
        self.assertEqual(result["status"], "dispatched")
        self.assertEqual(result["verification_status"], "pending")
        self.assertFalse(result["execution_permitted"])
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0], "automation.rab_android_bridge")

    async def test_high_risk_candidate_is_not_dispatched(self):
        high = {**self.candidate, "risk": "high"}
        decision = {**self.decision, "suggestion": {"action_id": "tap-settings"}}
        with patch("integrations.rab.runtime.rab.store.read_manifest", return_value={"capabilities":[{"id":"automation.rab_android_bridge","state":"executable"}]}), \
             patch("integrations.rab.runtime.rab.bridge.probe", return_value={"reachable": True}), \
             patch("src.rab_ui_controller.decide_ui", new=AsyncMock(return_value=decision)), \
             patch("integrations.rab.runtime.rab.runtime.execute") as execute:
            result = json.loads(await rab_ui_action("Delete account", {}, [high]))
        self.assertEqual(result["status"], "approval-required")
        execute.assert_not_called()

    async def test_missing_bridge_capability_blocks_before_model_call(self):
        with patch("integrations.rab.runtime.rab.store.read_manifest", return_value={"capabilities": []}), \
             patch("src.rab_ui_controller.decide_ui", new=AsyncMock()) as decide:
            result = json.loads(await rab_ui_action("Open settings", {}, [self.candidate]))
        self.assertEqual(result["status"], "awaiting-setup")
        decide.assert_not_called()

    async def test_unreachable_bridge_blocks_before_model_call(self):
        manifest = {"capabilities":[{"id":"automation.rab_android_bridge","state":"executable"}]}
        with patch("integrations.rab.runtime.rab.store.read_manifest", return_value=manifest), \
             patch("integrations.rab.runtime.rab.bridge.probe", return_value={"reachable": False}), \
             patch("src.rab_ui_controller.decide_ui", new=AsyncMock()) as decide:
            result = json.loads(await rab_ui_action("Open settings", {}, [self.candidate]))
        self.assertEqual(result["status"], "bridge-unavailable")
        decide.assert_not_called()

    async def test_escalation_without_selection_never_dispatches(self):
        blocked = {"system": "S2", "status": "needs-deliberation", "execution_permitted": False}
        with patch("integrations.rab.runtime.rab.store.read_manifest", return_value={"capabilities":[{"id":"automation.rab_android_bridge","state":"executable"}]}), \
             patch("integrations.rab.runtime.rab.bridge.probe", return_value={"reachable": True}), \
             patch("src.rab_ui_controller.decide_ui", new=AsyncMock(return_value=blocked)), \
             patch("integrations.rab.runtime.rab.runtime.execute") as execute:
            result = json.loads(await rab_ui_action("Open settings", {}, [self.candidate]))
        self.assertEqual(result["status"], "needs-deliberation")
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
