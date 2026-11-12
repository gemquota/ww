import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.canvas_browser import (
    _open_external_url,
    is_trusted_google_url,
    launch_canvas_browser,
    run_webview,
)


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

    def test_external_handler_only_accepts_http_urls(self):
        with patch("src.canvas_browser.shutil.which", return_value="/fake/termux-open-url"):
            with patch("src.canvas_browser.subprocess.Popen") as popen:
                self.assertTrue(_open_external_url("https://example.com/page"))
                popen.assert_called_once()
                self.assertFalse(_open_external_url("javascript:alert(1)"))
                self.assertFalse(_open_external_url("file:///etc/passwd"))

    def test_embedded_workspace_builds_webview_and_native_controls(self):
        instances = {}

        class FakeView:
            MATCH_PARENT = "MATCH_PARENT"
            WRAP_CONTENT = "WRAP_CONTENT"

            def __init__(self, activity, *args, **kwargs):
                self.activity = activity
                self.parent = args[0] if args else None
                self.id = id(self)
                self.calls = []
                instances.setdefault(type(self).__name__, []).append(self)

            def setlinearlayoutparams(self, value):
                self.calls.append(("weight", value))

            def setheight(self, value):
                self.calls.append(("height", value))

            def settext(self, value):
                self.calls.append(("text", value))

        class FakeLinearLayout(FakeView):
            pass

        class FakeTextView(FakeView):
            pass

        class FakeButton(FakeView):
            pass

        class FakeWebView(FakeView):
            def allowjavascript(self, value):
                self.calls.append(("javascript", value))

            def allownavigation(self, value):
                self.calls.append(("navigation", value))

            def loaduri(self, value):
                self.calls.append(("load", value))

            def goback(self):
                self.calls.append(("back",))

            def goforward(self):
                self.calls.append(("forward",))

        class FakeActivity:
            def __init__(self, connection, **kwargs):
                self.finished = False

            def finish(self):
                self.finished = True

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def events(self):
                done = instances["FakeButton"][-1]
                yield SimpleNamespace(
                    type="click", value={"id": done.id}
                )

        tg = SimpleNamespace(
            Connection=FakeConnection,
            Activity=FakeActivity,
            LinearLayout=FakeLinearLayout,
            TextView=FakeTextView,
            Button=FakeButton,
            WebView=FakeWebView,
            View=FakeView,
            Event=SimpleNamespace(
                destroy="destroy",
                back="back",
                click="click",
                webviewNavigation="navigation",
                webviewHTTPError="http_error",
                webviewError="error",
            ),
        )
        with patch.dict(sys.modules, {"termuxgui": tg}):
            self.assertEqual(run_webview(), 0)

        webview = instances["FakeWebView"][0]
        self.assertIsInstance(webview.parent, FakeLinearLayout)
        self.assertIn(("load", "https://gemini.google.com/app"), webview.calls)
        self.assertIn(("javascript", True), webview.calls)
        self.assertIn(("navigation", False), webview.calls)
        self.assertEqual(len(instances["FakeButton"]), 5)


if __name__ == "__main__":
    unittest.main()
