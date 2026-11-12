"""Optional Android WebView launcher for Gemini Canvas through Termux:GUI.

The Android WebView is the browser engine: it parses and renders HTML/CSS and
executes JavaScript. This module does not attempt to reimplement a browser.
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
    """Launch the Termux:GUI WebView helper using a Python runtime with termuxgui."""
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


def run_webview(url: str = CANVAS_URL) -> int:
    """Run the Android WebView in its own Activity."""
    try:
        import termuxgui as tg
    except ImportError as exc:
        raise RuntimeError("The termuxgui Python bindings are not installed.") from exc

    if not is_trusted_google_url(url):
        raise ValueError("Only HTTPS Google URLs may be loaded inside WW's WebView.")

    with tg.Connection() as connection:
        activity = tg.Activity(connection, intercept=True)
        webview = tg.WebView(activity)
        # Termux:GUI prompts the user before allowing JavaScript.
        webview.allowjavascript(True)
        # Keep navigation under WW's allowlist rather than granting arbitrary sites
        # access to this JavaScript-enabled WebView.
        webview.allownavigation(False)
        webview.loaduri(url)

        for event in connection.events():
            if event.type == tg.Event.destroy and event.value.get("finishing"):
                break
            if event.type == tg.Event.back:
                webview.goback()
            elif event.type == tg.Event.webviewNavigation:
                target = event.value.get("url", "")
                if is_trusted_google_url(target):
                    webview.loaduri(target)
                elif target.startswith(("https://", "http://")):
                    opener = shutil.which("termux-open-url")
                    if opener:
                        subprocess.Popen([opener, target])
                    else:
                        print(f"Blocked external navigation: {target}", file=sys.stderr)
            elif event.type == tg.Event.webviewHTTPError:
                print(
                    f"Gemini WebView HTTP error {event.value.get('code')}: "
                    f"{event.value.get('url', '')}",
                    file=sys.stderr,
                )
            elif event.type == tg.Event.webviewError:
                print(
                    f"Gemini WebView failed to load: {event.value.get('url', '')}",
                    file=sys.stderr,
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Open Gemini in a Termux:GUI WebView.")
    parser.add_argument("url", nargs="?", default=CANVAS_URL)
    args = parser.parse_args(argv)
    return run_webview(args.url)


if __name__ == "__main__":
    raise SystemExit(main())
