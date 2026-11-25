import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src import ui_controller


class ControllerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "experience.sqlite3"
        self.observation = {"app": "demo", "screen": "home", "private_text": "ignored"}

    def tearDown(self):
        self.temp.cleanup()

    def test_feedback_is_retrievable_for_candidate_actions(self):
        ui_controller.record_feedback(
            objective="Navigate settings", observation=self.observation,
            action_id="settings", outcome="success", db_path=self.db,
        )
        summary = ui_controller.experience_summary(
            self.observation,
            [{"id": "settings", "description": "Open settings", "risk": "low"}],
            self.db,
        )
        self.assertEqual(summary["known"]["settings"]["success"], 1)
        self.assertNotIn("private_text", summary["state_key"])

    def test_repeated_failures_escalate_system_one_suggestion(self):
        for _ in range(2):
            ui_controller.record_feedback(
                objective="Navigate settings", observation=self.observation,
                action_id="settings", outcome="failure", db_path=self.db,
            )
        suggestion = {"status": "suggest", "action_id": "settings", "reasons": []}
        with patch.object(ui_controller, "jev_enabled", return_value=True):
            with patch.object(ui_controller, "decide_ui_action", new=AsyncMock(return_value=suggestion)):
                async_result = ui_controller.decide(
                    objective="Navigate settings", observation=self.observation,
                    candidates=[{"id":"settings","description":"Open settings","risk":"low"}],
                    db_path=self.db,
                )
                import asyncio
                result = asyncio.run(async_result)
        self.assertEqual(result["status"], "needs-deliberation")
        self.assertIn("negative-experience", result["system1"]["reasons"])


    def test_system_two_can_select_only_supplied_candidate(self):
        import asyncio
        async def deliberate(objective, observation, candidates, memory):
            return {"action_id": "settings", "rationale": "Best reversible step"}
        with patch.object(ui_controller, "jev_enabled", return_value=False):
            result = asyncio.run(ui_controller.decide(
                objective="Navigate settings", observation=self.observation,
                candidates=[{"id":"settings","description":"Open settings","risk":"low"}],
                system2=deliberate, db_path=self.db,
            ))
        self.assertEqual(result["system"], "S2")
        self.assertEqual(result["status"], "suggest")
        self.assertFalse(result["execution_permitted"])

    def test_system_two_failure_fails_closed(self):
        import asyncio
        async def broken(*args):
            raise RuntimeError("offline")
        with patch.object(ui_controller, "jev_enabled", return_value=False):
            result = asyncio.run(ui_controller.decide(
                objective="Navigate settings", observation=self.observation,
                candidates=[{"id":"settings","description":"Open settings","risk":"low"}],
                system2=broken, db_path=self.db,
            ))
        self.assertEqual(result["status"], "deliberation-unavailable")
        self.assertFalse(result["execution_permitted"])

    def test_without_system_two_escalation_does_not_execute(self):
        import asyncio
        with patch.object(ui_controller, "jev_enabled", return_value=False):
            result = asyncio.run(ui_controller.decide(
                objective="Navigate settings", observation=self.observation,
                candidates=[{"id":"settings","description":"Open settings","risk":"low"}],
                db_path=self.db,
            ))
        self.assertEqual(result["status"], "needs-deliberation")
        self.assertFalse(result["execution_permitted"])


if __name__ == "__main__":
    unittest.main()
