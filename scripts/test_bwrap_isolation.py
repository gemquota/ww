"""Initial adversarial smoke suite for a Linux Bubblewrap host.

This is a manual host-side test, not a sandbox implementation. It never runs on
Android/Termux and never marks a backend accepted. Tests assert host-observed
state where possible; unsupported controls remain explicitly unverified.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


def _python_inside_root() -> str | None:
    candidate = shutil.which("python3")
    if not candidate:
        return None
    path = Path(candidate).resolve()
    try:
        path.relative_to(Path("/usr").resolve())
    except ValueError:
        return None
    return str(path)


def _base_command(bwrap: str, python: str, code: str) -> list[str]:
    # Construct a deliberately small root. Only /usr is exposed, read-only.
    # /tmp is a fresh tmpfs, /proc belongs to the new PID namespace, and /dev
    # is a minimal device mount. No host home, /etc, /run or workspace is bound.
    return [
        bwrap,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--dir", "/usr",
        "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin",
        "--symlink", "usr/sbin", "/sbin",
        "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64",
        "--dir", "/tmp",
        "--tmpfs", "/tmp",
        "--dev", "/dev",
        "--proc", "/proc",
        "--clearenv",
        "--setenv", "PATH", "/usr/bin:/bin",
        "--chdir", "/tmp",
        "--",
        python,
        "-c",
        code,
    ]


def _run(bwrap: str, python: str, code: str, *, timeout: float = 8.0) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WW_SANDBOX_HOST_SECRET_PROBE"] = "must-not-cross-boundary"
    command = _base_command(bwrap, python, code)
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return subprocess.CompletedProcess(command, 124, stdout, stderr + "\nprobe timed out")
    except OSError as exc:
        return subprocess.CompletedProcess(command, 125, "", f"{type(exc).__name__}: {exc}")


def _case(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed", "detail": detail}


def run_suite() -> dict[str, Any]:
    if sys.platform != "linux":
        return {
            "schema": 1,
            "result": "not_run",
            "sandbox_accepted": False,
            "reason": "This suite is for a Linux host; it is not a Termux/Android test.",
            "tests": [],
        }

    bwrap = shutil.which("bwrap")
    python = _python_inside_root()
    if not bwrap or not python:
        return {
            "schema": 1,
            "result": "not_run",
            "sandbox_accepted": False,
            "reason": "Bubblewrap or a Python interpreter under /usr is unavailable.",
            "tests": [],
        }

    try:
        smoke = _run(bwrap, python, "print('ww-bwrap-ready')")
    except (OSError, subprocess.TimeoutExpired) as exc:
        smoke = None
        smoke_error = type(exc).__name__
    else:
        smoke_error = None

    if smoke is None or smoke.returncode != 0 or smoke.stdout.strip() != "ww-bwrap-ready":
        detail = smoke_error or (smoke.stderr.strip()[-500:] if smoke else "no result")
        return {
            "schema": 1,
            "result": "not_run",
            "sandbox_accepted": False,
            "reason": f"Bubblewrap preflight failed: {detail}",
            "tests": [],
        }

    tests: list[dict[str, Any]] = []

    # A host-only sentinel is placed under /tmp. The sandbox receives a fresh
    # /tmp tmpfs, so it must not be able to read the host file.
    with tempfile.TemporaryDirectory(prefix="ww-host-sentinel-") as host_tmp:
        sentinel = Path(host_tmp) / "outside.txt"
        original = "host-secret-sentinel"
        sentinel.write_text(original, encoding="utf-8")
        code = (
            "from pathlib import Path\n"
            f"p = Path({str(sentinel)!r})\n"
            "try:\n"
            "    p.read_text()\n"
            "except OSError:\n"
            "    print('denied')\n"
            "else:\n"
            "    print('readable')\n"
        )
        result = _run(bwrap, python, code)
        unchanged = sentinel.read_text(encoding="utf-8") == original
        tests.append(_case(
            "host_filesystem_sentinel_hidden",
            result.returncode == 0 and result.stdout.strip() == "denied" and unchanged,
            "Sandbox could not read the host sentinel; host-side contents were rechecked.",
        ))

    # Verify that the new network namespace cannot reach a listener bound on
    # the host loopback interface. The listener is created and observed outside.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(0.5)
    host_port = listener.getsockname()[1]
    accepted: list[bool] = []

    def accept_once() -> None:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        accepted.append(True)
        conn.close()

    accept_thread = threading.Thread(target=accept_once, daemon=True)
    accept_thread.start()
    net_code = (
        "import socket\n"
        "s = socket.socket()\n"
        "s.settimeout(0.75)\n"
        "try:\n"
        f"    s.connect(('127.0.0.1', {host_port}))\n"
        "except OSError:\n"
        "    print('blocked')\n"
        "else:\n"
        "    print('connected')\n"
        "finally:\n"
        "    s.close()\n"
    )
    net_result = _run(bwrap, python, net_code)
    accept_thread.join(timeout=1.0)
    listener.close()
    tests.append(_case(
        "host_loopback_unreachable",
        net_result.returncode == 0 and net_result.stdout.strip() == "blocked" and not accepted,
        "A host loopback listener was not reachable from the sandbox network namespace.",
    ))

    # The host process remains alive, but must not appear in the sandbox's
    # PID namespace / proc mount.
    sleeper = subprocess.Popen(
        ["sleep", "30"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        pid_code = (
            "from pathlib import Path\n"
            f"print('visible' if Path('/proc/{sleeper.pid}').exists() else 'hidden')\n"
        )
        pid_result = _run(bwrap, python, pid_code)
        host_alive = sleeper.poll() is None
        tests.append(_case(
            "host_process_hidden",
            pid_result.returncode == 0 and pid_result.stdout.strip() == "hidden" and host_alive,
            "The host process remained alive but was absent from the sandbox PID namespace.",
        ))
    finally:
        sleeper.terminate()
        try:
            sleeper.wait(timeout=2)
        except subprocess.TimeoutExpired:
            sleeper.kill()
            sleeper.wait(timeout=2)

    # --clearenv must prevent a deliberately supplied parent environment value
    # from entering the sandbox.
    env_result = _run(
        bwrap,
        python,
        "import os; print('absent' if 'WW_SANDBOX_HOST_SECRET_PROBE' not in os.environ else 'present')",
    )
    tests.append(_case(
        "host_environment_secret_not_inherited",
        env_result.returncode == 0 and env_result.stdout.strip() == "absent",
        "A sentinel environment variable supplied to the Bubblewrap parent was absent inside.",
    ))

    failed = [test for test in tests if test["status"] != "passed"]
    return {
        "schema": 1,
        "result": "passed_smoke_suite" if not failed else "failed",
        "sandbox_accepted": False,
        "host": {"system": sys.platform, "machine": os.uname().machine},
        "backend": {"name": "bubblewrap", "path_available": True},
        "tests": tests,
        "not_verified": [
            "cgroup-enforced CPU, memory, process-count, file-size and descriptor limits",
            "descendant cleanup after parent crash, cancellation and output overflow",
            "raw-syscall, openat/descriptor, hard-link and mount-escape resistance",
            "IPv6, UDP, DNS, Unix sockets and public/private egress",
            "secret-bearing inherited file descriptors and host control sockets",
            "audit durability, redaction and crash recovery",
        ],
        "acceptance_note": (
            "Passing these smoke tests is necessary but insufficient. "
            "sandbox_accepted is deliberately fixed to false until the full "
            "platform-specific adversarial suite and resource controls pass."
        ),
    }


def main() -> int:
    report = run_suite()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["result"] == "passed_smoke_suite":
        return 0
    if report["result"] == "not_run":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
