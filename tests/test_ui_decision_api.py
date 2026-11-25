import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src.dashboard import app as dashboard


class JevUIDecisionAPITests(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_returns_advisory_decision(self):
        expected = {
            "status": "suggest",
            "action_id": "open-settings",
            "confidence": 0.96,
            "execution_permitted": False,
        }
        request = dashboard.UIDecisionRequest(
            objective="Open settings",
            observation={"screen": "home"},
            candidates=[
                {"id": "open-settings", "description": "Open settings", "risk": "low"}
            ],
        )
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}):
            with patch.object(dashboard, "decide_ui_action", return_value=expected):
                result = await dashboard.decide_ui(request)
        self.assertEqual(result, expected)
        self.assertFalse(result["execution_permitted"])

    async def test_endpoint_is_unavailable_without_jev_key(self):
        request = dashboard.UIDecisionRequest(
            objective="Open settings",
            observation={},
            candidates=[{"id": "open", "description": "Open settings", "risk": "low"}],
        )
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}):
            with self.assertRaises(HTTPException) as raised:
                await dashboard.decide_ui(request)
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
