import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dashboard import app as dashboard


class FakeWWClient:
    instances = []

    def __init__(self):
        self.connected = False
        self.closed = False
        self.active_chat_id = "fake-chat"
        self.primary_cookie = os.getenv("SECURE_1PSID", "")
        self.__class__.instances.append(self)

    async def connect(self):
        self.connected = True

    async def close(self):
        self.closed = True


class DashboardRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_session_uses_shared_ww_client_and_runtime(self):
        FakeWWClient.instances.clear()
        with tempfile.TemporaryDirectory() as directory:
            cookie_path = Path(directory) / "cookies.txt"
            cookie_path.write_text("cookie export", encoding="utf-8")
            with patch.dict(os.environ, {
                "SECURE_1PSID": "",
                "WW_COOKIE_FILE": str(cookie_path),
            }):
                with patch.object(dashboard, "extract_gemini_cookies", return_value={
                    "SECURE_1PSID": "primary-cookie",
                }):
                    with patch.object(dashboard, "WWClient", FakeWWClient):
                        session = await dashboard._create_browser_client("test-session")

            self.assertTrue(session.client.connected)
            self.assertEqual(session.client.primary_cookie, "primary-cookie")
            self.assertIs(session.runtime.client, session.client)
            self.assertEqual(session.runtime.workspace_root, dashboard.WORKSPACE_ROOT)
            await session.close()
            self.assertTrue(session.client.closed)

    async def test_runtime_status_checks_cookie_contents_not_just_file_presence(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_path = Path(directory) / "cookies.txt"
            cookie_path.write_text("invalid", encoding="utf-8")
            with patch.dict(os.environ, {
                "SECURE_1PSID": "",
                "WW_COOKIE_FILE": str(cookie_path),
            }):
                with patch.object(dashboard, "extract_gemini_cookies", return_value={}):
                    status = await dashboard.runtime_status()
            self.assertFalse(status["gemini_credentials_configured"])
            self.assertIn("conversation-runtime", status["features"])


if __name__ == "__main__":
    unittest.main()
