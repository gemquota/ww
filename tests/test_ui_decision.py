import os
import unittest
from unittest.mock import patch

from src import ui_decision


class JevUIDecisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_low_risk_confident_action_is_suggested_not_executed(self):
        response = {
            "model": "jev-test",
            "answers": {
                "next_action": {
                    "choice": "open-menu",
                    "probabilities": {"open-menu": 0.98, "cancel": 0.02},
                    "confidence": 0.98,
                },
                "needs_deliberation": {"noul": 0.01},
            },
            "usage": {"input_tokens": 20, "output_tokens": 0},
        }
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}):
            with patch("src.ui_decision._request", return_value=response):
                result = await ui_decision.decide_ui_action(
                    objective="Open the settings menu",
                    observation={"screen": "home"},
                    candidates=[
                        {"id": "open-menu", "description": "Open settings", "risk": "low"},
                        {"id": "cancel", "description": "Cancel current operation", "risk": "low"},
                    ],
                )
        self.assertEqual(result["status"], "suggest")
        self.assertEqual(result["action_id"], "open-menu")
        self.assertFalse(result["execution_permitted"])

    async def test_high_risk_action_always_escalates(self):
        response = {
            "model": "jev-test",
            "answers": {
                "next_action": {"choice": "delete", "confidence": 0.99, "probabilities": {"delete": 1.0}},
                "needs_deliberation": {"noul": 0.0},
            },
        }
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}):
            with patch("src.ui_decision._request", return_value=response):
                result = await ui_decision.decide_ui_action(
                    objective="Remove an item",
                    observation={"screen": "item"},
                    candidates=[{"id": "delete", "description": "Delete item", "risk": "high"}],
                )
        self.assertEqual(result["status"], "escalate")
        self.assertIn("high-risk-action", result["reasons"])
        self.assertFalse(result["execution_permitted"])

    async def test_missing_key_fails_closed(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            with self.assertRaises(ui_decision.JevConfigurationError):
                await ui_decision.decide_ui_action(
                    objective="Open settings",
                    observation={},
                    candidates=[{"id": "open", "description": "Open settings", "risk": "low"}],
                )

    async def test_rejects_unknown_model_action(self):
        response = {
            "answers": {
                "next_action": {"choice": "not-a-candidate", "confidence": 1.0},
                "needs_deliberation": {"noul": 0.0},
            }
        }
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}):
            with patch("src.ui_decision._request", return_value=response):
                with self.assertRaises(ui_decision.JevRequestError):
                    await ui_decision.decide_ui_action(
                        objective="Open settings",
                        observation={},
                        candidates=[{"id": "open", "description": "Open settings", "risk": "low"}],
                    )


if __name__ == "__main__":
    unittest.main()
