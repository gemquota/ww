import unittest
from unittest.mock import patch

from src.cookie_loader import load_cookie_environment


class CookieEnvironmentTests(unittest.TestCase):
    def test_cookie_file_fills_blank_values_but_preserves_explicit_values(self):
        environment = {
            "SECURE_1PSID": "",
            "SECURE_1PSIDTS": "explicit-timestamp",
        }
        with patch("src.cookie_loader.extract_gemini_cookies", return_value={
            "SECURE_1PSID": "file-primary",
            "SECURE_1PSIDTS": "file-timestamp",
        }):
            loaded = load_cookie_environment("unused", environment)

        self.assertEqual(environment["SECURE_1PSID"], "file-primary")
        self.assertEqual(environment["SECURE_1PSIDTS"], "explicit-timestamp")
        self.assertEqual(loaded["SECURE_1PSID"], "file-primary")


if __name__ == "__main__":
    unittest.main()
