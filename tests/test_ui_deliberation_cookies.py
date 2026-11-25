import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.ui_deliberation import deliberate_ui_action


class SystemTwoCookieTests(unittest.IsolatedAsyncioTestCase):
    async def test_loads_netscape_cookies_before_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            cookie_file = Path(directory) / "cookies.txt"
            cookie_file.write_text(
                "# Netscape HTTP Cookie File\n"
                ".google.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tprimary-test\n"
                "#HttpOnly_.google.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSIDTS\ttimestamp-test\n",
                encoding="utf-8",
            )
            fake = SimpleNamespace(
                connect=AsyncMock(),
                ask_output=AsyncMock(return_value=SimpleNamespace(
                    text='{"action_id":"open","rationale":"safe"}'
                )),
                close=AsyncMock(),
            )
            with patch.dict(os.environ, {"WW_COOKIE_FILE": str(cookie_file)}, clear=True):
                with patch("src.ui_deliberation.WWClient", return_value=fake):
                    result = await deliberate_ui_action(
                        "Open settings", {"screen": "home"},
                        [{"id": "open", "description": "Open settings", "risk": "low"}],
                        {"known": {}},
                    )
                    self.assertEqual(os.environ["SECURE_1PSID"], "primary-test")
                    self.assertEqual(os.environ["SECURE_1PSIDTS"], "timestamp-test")
            self.assertEqual(result["action_id"], "open")
            fake.connect.assert_awaited_once()
            fake.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
