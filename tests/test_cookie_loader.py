import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cookie_loader import extract_gemini_cookies, load_cookie_environment


class CookieEnvironmentTests(unittest.TestCase):
    def test_extracts_google_primary_and_youtube_scoped_timestamp_cookie(self):
        content = "\n".join([
            "# Netscape HTTP Cookie File",
            ".google.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tprimary-test",
            ".youtube.com\tTRUE\t/\tTRUE\t0\t__Secure-1PSIDTS\ttimestamp-test",
            ".crushon.ai\tTRUE\t/\tTRUE\t0\t__Secure-1PSID\tshould-not-load",
            "",
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cookies.txt"
            path.write_text(content)
            loaded = extract_gemini_cookies(path)
        self.assertEqual(loaded, {
            "SECURE_1PSID": "primary-test",
            "SECURE_1PSIDTS": "timestamp-test",
        })

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
