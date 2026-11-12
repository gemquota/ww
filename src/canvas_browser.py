"""Native Android Canvas workspace for WW, backed by Termux:GUI WebView.

The WebView is embedded in a WW-owned Android Activity with native navigation
controls. Gemini itself remains the web application; WW does not emulate Canvas.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

CANVAS_URL = "https://gemini.google.com/app"


def is_trusted_google_url(url: str) -> bool:
    """Keep the embedded WebView on Google-owned hosts used by Gemini and sign-in."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if parsed.scheme != "https" or not host:
        return False
    return (
        host == "google.com"
        or host.endswith(".google.com")
        or host.endswith(".googleusercontent.com")
        or host.endswith(".gstatic.com")
        or host.endswith(".googleapis.com")
        or host in {"g.co", "goo.gl"}
    )


def _shared_home_path(path: Path) -> Path:
    """Translate a proot --shared-home path back to the real Termux home path."""
    home = Path.home().resolve()
    try:
        relative = path.resolve().relative_to(home)
    except ValueError:
        return path.resolve()
    termux_home = Path(os.getenv(
        "WW_TERMUX_HOME", "/data/data/com.termux/files/home"
    ))
    return termux_home / relative


def _python_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.getenv("WW_TERMUX_PYTHON")
    if explicit:
        candidates.append(Path(explicit))
    prefix = os.getenv("PREFIX")
    if prefix:
        candidates.append(Path(prefix) / "bin" / "python")
    candidates.extend(
        [
            Path("/data/data/com.termux/files/usr/bin/python"),
            Path("/data/user/0/com.termux/files/usr/bin/python"),
            Path(sys.executable),
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen and candidate.is_file():
            seen.add(key)
            unique.append(candidate)
    return unique


def launch_canvas_browser(url: str = CANVAS_URL) -> Path:
    """Launch the native WW Canvas Activity using a Termux Python runtime."""
    if not is_trusted_google_url(url):
        raise ValueError("WW's embedded Canvas browser only accepts HTTPS Google URLs.")

    script = _shared_home_path(Path(__file__))
    for interpreter in _python_candidates():
        prefix = interpreter.parent.parent
        env = os.environ.copy()
        env["PREFIX"] = str(prefix)
        env["PATH"] = str(prefix / "bin") + os.pathsep + env.get("PATH", "")
        try:
            check = subprocess.run(
                [str(interpreter), "-c", "import termuxgui"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if check.returncode != 0:
            continue
        subprocess.Popen(
            [str(interpreter), str(script), url],
            env=env,
            start_new_session=True,
        )
        return interpreter

    raise RuntimeError(
        "Termux:GUI's Python bindings are not available. Install the Termux:GUI "
        "Android add-on, then in regular Termux (outside Debian) run: "
        "python -m pip install termuxgui. If needed, set WW_TERMUX_PYTHON to "
        "the Termux host Python path."
    )


def _open_external_url(url: str) -> bool:
    """Hand ordinary web links to Android's browser, never to the JS-enabled WebView."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return False
    opener = shutil.which("termux-open-url")
    if not opener:
        return False
    subprocess.Popen([opener, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def run_webview(url: str = CANVAS_URL) -> int:
    """Run Gemini in a native WW Activity with an embedded Android WebView."""
    try:
        import termuxgui as tg
    except ImportError as exc:
        raise RuntimeError("The termuxgui Python bindings are not installed.") from exc

    if not is_trusted_google_url(url):
        raise ValueError("Only HTTPS Google URLs may be loaded inside WW's WebView.")

    with tg.Connection() as connection:
        activity = tg.Activity(connection, intercept=True)
        root = tg.LinearLayout(activity)

        toolbar = tg.LinearLayout(activity, root, False)
        toolbar.setlinearlayoutparams(0)
        toolbar.setheight(tg.View.WRAP_CONTENT)

        title = tg.TextView(activity, "WW  /  GEMINI CANVAS", toolbar)
        title.setlinearlayoutparams(1)
        title.setheight(tg.View.WRAP_CONTENT)

        back_button = tg.Button(activity, "Back", toolbar)
        forward_button = tg.Button(activity, "Forward", toolbar)
        reload_button = tg.Button(activity, "Reload", toolbar)
        home_button = tg.Button(activity, "Gemini", toolbar)
        done_button = tg.Button(activity, "Done", toolbar)
        for button in (back_button, forward_button, reload_button, home_button, done_button):
            button.setlinearlayoutparams(0)
            button.setheight(tg.View.WRAP_CONTENT)

        status = tg.TextView(activity, "Connecting to Gemini…", root)
        status.setlinearlayoutparams(0)
        status.setheight(tg.View.WRAP_CONTENT)

        webview = tg.WebView(activity, root)
        webview.setlinearlayoutparams(1)
        webview.setheight(0)  # Weight 1 fills the remaining Activity height.

        footer = tg.TextView(
            activity,
            "Canvas runs here. Your WW terminal session stays available in the background.",
            root,
        )
        footer.setlinearlayoutparams(0)
        footer.setheight(tg.View.WRAP_CONTENT)

        # Termux:GUI asks the user before granting JavaScript. Navigation remains
        # host-controlled so untrusted sites never inherit this WebView's JS context.
        webview.allowjavascript(True)
        webview.allownavigation(False)
        current_url = url
        webview.loaduri(current_url)
        status.settext("Gemini Canvas")

        for event in connection.events():
            if event.type == tg.Event.destroy and event.value.get("finishing"):
                break

            if event.type == tg.Event.back:
                try:
                    webview.goback()
                    status.settext("Navigating back")
                except Exception:
                    activity.finish()
                    break
                continue

            if event.type == tg.Event.click:
                clicked = event.value.get("id")
                if clicked == back_button:
                    webview.goback()
                    continue
                if clicked == forward_button:
                    webview.goforward()
                    continue
                if clicked == reload_button:
                    webview.loaduri(current_url)
                    status.settext("Reloading Gemini…")
                    continue
                if clicked == home_button:
                    current_url = CANVAS_URL
                    webview.loaduri(current_url)
                    status.settext("Gemini Canvas")
                    continue
                if clicked == done_button:
                    activity.finish()
                    break
                continue

            if event.type == tg.Event.webviewNavigation:
                target = event.value.get("url", "")
                if is_trusted_google_url(target):
                    current_url = target
                    webview.loaduri(target)
                    status.settext("Gemini Canvas")
                elif _open_external_url(target):
                    status.settext("Opened external link in Android browser")
                else:
                    status.settext("External link blocked: no Android URL handler")

            elif event.type == tg.Event.webviewHTTPError:
                status.settext(
                    f"HTTP {event.value.get('code', '?')} while loading Gemini"
                )
                print(
                    f"Gemini WebView HTTP error {event.value.get('code')}: "
                    f"{event.value.get('url', '')}",
                    file=sys.stderr,
                )
            elif event.type == tg.Event.webviewError:
                status.settext("Gemini page failed to load")
                print(
                    f"Gemini WebView failed to load: {event.value.get('url', '')}",
                    file=sys.stderr,
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Open Gemini in WW's native Termux:GUI Canvas workspace."
    )
    parser.add_argument("url", nargs="?", default=CANVAS_URL)
    args = parser.parse_args(argv)
    return run_webview(args.url)


if __name__ == "__main__":
    raise SystemExit(main())
