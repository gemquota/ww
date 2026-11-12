import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.canvas_browser import is_trusted_google_url, launch_canvas_browser


class CanvasBrowserTests(unittest.TestCase):
    def test_trusts_https_google_hosts_only(self):
        self.assertTrue(is_trusted_google_url("https://gemini.google.com/app"))
        self.assertTrue(is_trusted_google_url("https://accounts.google.com/"))
        self.assertTrue(is_trusted_google_url("https://lh3.googleusercontent.com/image"))
        self.assertFalse(is_trusted_google_url("http://gemini.google.com/app"))
        self.assertFalse(is_trusted_google_url("https://example.com/"))
        self.assertFalse(is_trusted_google_url("javascript:alert(1)"))

    def test_launch_uses_termuxgui_python_runtime(self):
        interpreter = Path("/fake/termux/python")
        with (
            patch("src.canvas_browser._python_candidates", return_value=[interpreter]),
            patch("src.canvas_browser.subprocess.run", return_value=SimpleNamespace(returncode=0)),
            patch("src.canvas_browser.subprocess.Popen") as popen,
        ):
            selected = launch_canvas_browser()
        self.assertEqual(selected, interpreter)
        args = popen.call_args.args[0]
        self.assertEqual(args[0], str(interpreter))
        self.assertTrue(args[1].endswith("src/canvas_browser.py"))
        self.assertEqual(args[2], "https://gemini.google.com/app")

    def test_refuses_non_google_urls(self):
        with self.assertRaises(ValueError):
            launch_canvas_browser("https://example.com")


if __name__ == "__main__":
    unittest.main()
