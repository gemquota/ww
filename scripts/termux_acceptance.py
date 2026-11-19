"""Consolidated WW acceptance check for Termux and Debian PRoot.

Run from the repository root after installing requirements-dashboard.txt:
    python -m scripts.termux_acceptance

This exercises the local backend without making a live Gemini request. The
authenticated Gemini conversation/tool round-trip still requires the manual
browser acceptance sequence documented in docs/architecture-review.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from unittest.mock import patch


def check(label: str, condition: bool, detail: str = "") -> None:
    marker = "PASS" if condition else "FAIL"
    print(f"[{marker}] {label}" + (f": {detail}" if detail else ""))
    if not condition:
        raise RuntimeError(f"Acceptance check failed: {label}")


def run_unit_suite(repo: Path) -> None:
    print("\n== Unit and deterministic integration suite ==")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=600,
        check=False,
    )
    print(result.stdout)
    check("unittest suite", result.returncode == 0, f"exit={result.returncode}")


async def check_process_backend(workspace: Path) -> None:
    from src.tools.system_tools import _run_process

    print("\n== Process backend ==")
    stdout, stderr, returncode = await _run_process(
        sys.executable,
        "-c",
        "import os,sys; print(os.getcwd()); print(sys.version_info.major)",
        cwd=workspace,
        timeout=10,
    )
    output = stdout.decode(errors="replace").splitlines()
    check("subprocess working directory", output[0] == str(workspace))
    check("subprocess Python", output[1] == str(sys.version_info.major))
    check("subprocess exit status", returncode == 0, f"stderr={stderr.decode(errors='replace')}")

    stubborn = (
        "import os,signal,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "os.close(1); os.close(2); time.sleep(60)"
    )
    started = time.monotonic()
    try:
        await _run_process(sys.executable, "-c", stubborn, cwd=workspace, timeout=0.25)
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - started
        check("timeout kills process after pipe closure", elapsed < 5, f"{elapsed:.2f}s")
    else:
        check("timeout kills process after pipe closure", False, "process unexpectedly completed")


def check_workspace_tools(workspace: Path) -> None:
    from src.tools.system_tools import file_patch, read_file, write_file

    print("\n== Workspace tools ==")
    with patch("src.tools.system_tools._get_workspace_root", return_value=workspace):
        write_result = write_file("acceptance.txt", "WW workspace check")
        read_result = read_file("acceptance.txt")
        patch_result = file_patch("acceptance.txt", "workspace", "runtime")

    check("atomic workspace write", "SUCCESS" in write_result, write_result)
    check("bounded workspace read", "WW workspace check" in read_result, read_result[:160])
    check("workspace patch", "SUCCESS" in patch_result, patch_result)
    check(
        "workspace file contents",
        (workspace / "acceptance.txt").read_text(encoding="utf-8") == "WW runtime check",
    )


def check_local_api(repo: Path) -> None:
    print("\n== Local browser API ==")
    with tempfile.TemporaryDirectory(prefix="ww-api-acceptance-") as directory:
        workspace = Path(directory)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]

        api_key = secrets.token_urlsafe(32)
        environment = os.environ.copy()
        environment.update({
            "WW_DASHBOARD_API_KEY": api_key,
            "WW_WORKSPACE": str(workspace),
            "WW_EXECUTION_BACKEND": "proot-distro",
            "SECURE_1PSID": "acceptance-placeholder-not-a-real-cookie",
            "WW_CORS_ORIGINS": "https://gemquota.github.io",
        })
        log = tempfile.TemporaryFile(mode="w+t")
        server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "src.dashboard.app:app",
                "--host", "127.0.0.1", "--port", str(port),
            ],
            cwd=repo,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        base = f"http://127.0.0.1:{port}"
        headers = {"X-API-Key": api_key}
        try:
            response = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    break
                try:
                    request = Request(base + "/api/v1/health", headers=headers)
                    with urlopen(request, timeout=1) as result:
                        response = json.loads(result.read().decode("utf-8"))
                    break
                except (URLError, TimeoutError):
                    time.sleep(0.2)

            if response is None:
                log.seek(0)
                raise RuntimeError("Local API failed to start:\n" + log.read()[-5000:])

            check("authenticated API health", response.get("status") == "ok", str(response))

            request = Request(base + "/api/v1/runtime", headers=headers)
            with urlopen(request, timeout=3) as result:
                runtime = json.loads(result.read().decode("utf-8"))
            check("runtime workspace", runtime.get("workspace") == workspace.name)
            check("runtime backend", runtime.get("execution_backend") == "proot-distro")
            check("credential readiness reporting", runtime.get("gemini_credentials_configured") is True)

            with urlopen(base + "/chat-ui", timeout=3) as result:
                html = result.read().decode("utf-8")
            check("browser workspace served", "WW" in html and "Backend connection" in html)

            try:
                with urlopen(base + "/api/v1/runtime", timeout=3):
                    unauthorized = False
            except HTTPError as error:
                unauthorized = error.code == 401
            check("API rejects missing key", unauthorized)

            preflight = Request(
                base + "/api/v1/runtime",
                method="OPTIONS",
                headers={
                    "Origin": "https://gemquota.github.io",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "x-api-key",
                },
            )
            with urlopen(preflight, timeout=3) as result:
                cors_origin = result.headers.get("Access-Control-Allow-Origin")
            check("Pages CORS allowlist", cors_origin == "https://gemquota.github.io", str(cors_origin))
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            log.close()


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run WW Termux/PRoot acceptance checks.")
    parser.add_argument(
        "--skip-tests", action="store_true",
        help="Skip unittest discovery (useful when CI has already run it).",
    )
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parent.parent
    print("WW Termux / PRoot acceptance")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform: {sys.platform} / {os.name}")
    print(f"Repository: {repo}")

    if not args.skip_tests:
        run_unit_suite(repo)
    with tempfile.TemporaryDirectory(prefix="ww-workspace-acceptance-") as directory:
        workspace = Path(directory)
        await check_process_backend(workspace)
        check_workspace_tools(workspace)
    check_local_api(repo)

    print("\nAll automated acceptance checks passed.")
    print("This does not authenticate to Gemini or prove the live browser tool round-trip.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"\nACCEPTANCE FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
