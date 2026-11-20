import os
import unittest
from unittest.mock import AsyncMock, patch

from src.tools.system_tools import shell_exec


class ShellEnvironmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_shell_child_does_not_inherit_gemini_or_dashboard_credentials(self):
        fake_run = AsyncMock(return_value=(b"ok", b"", 0))
        secrets = {
            "SECURE_1PSID": "cookie-value",
            "SECURE_1PSIDTS": "timestamp-value",
            "GEMINI_API_KEY": "gemini-secret",
            "GOOGLE_API_KEY": "google-secret",
            "WW_DASHBOARD_API_KEY": "dashboard-secret",
            "WW_DASHBOARD_API_KEYS": "dashboard-secret-2",
            "GH_TOKEN": "preserve-git-auth",
            "PATH": "/usr/bin",
        }
        with patch.dict(os.environ, secrets, clear=True):
            with patch("src.tools.system_tools._run_process", fake_run):
                result = await shell_exec("printf ok")

        self.assertIn("ok", result)
        child_env = fake_run.await_args.kwargs["env"]
        for name in (
            "SECURE_1PSID", "SECURE_1PSIDTS", "GEMINI_API_KEY",
            "GOOGLE_API_KEY", "WW_DASHBOARD_API_KEY", "WW_DASHBOARD_API_KEYS",
        ):
            self.assertNotIn(name, child_env)
        self.assertEqual(child_env["GH_TOKEN"], "preserve-git-auth")
        self.assertEqual(child_env["PATH"], "/usr/bin")


if __name__ == "__main__":
    unittest.main()
