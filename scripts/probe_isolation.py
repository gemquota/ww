"""Non-invasive host capability inventory for Phase 2C.

This command does not launch a sandbox or execute untrusted code. Its output is
diagnostic evidence only; it can never mark a host as sandbox-accepted.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def _namespace_inventory(proc: Path) -> dict[str, bool]:
    names = ("user", "mnt", "pid", "net", "ipc", "cgroup")
    return {name: (proc / "self" / "ns" / name).exists() for name in names}


def collect_report(
    *,
    proc_root: str | Path = "/proc",
    sys_root: str | Path = "/sys",
    executable_lookup=shutil.which,
) -> dict[str, Any]:
    """Collect read-only host indicators without attempting privileged actions."""
    proc = Path(proc_root)
    sysfs = Path(sys_root)
    status = _read(proc / "self" / "status") or ""
    seccomp = None
    for line in status.splitlines():
        if line.startswith("Seccomp:"):
            try:
                seccomp = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
            break

    controllers = _read(sysfs / "fs" / "cgroup" / "cgroup.controllers")
    max_user_ns = _read(Path("/proc/sys/user/max_user_namespaces"))
    unprivileged_userns = _read(Path("/proc/sys/kernel/unprivileged_userns_clone"))
    android_api = getattr(sys, "getandroidapilevel", lambda: None)()

    proot_markers = (
        "PROOT_TMP_DIR" in os.environ,
        "PROOT_LOADER" in os.environ,
        "proot" in (os.environ.get("LD_PRELOAD", "").lower()),
    )

    try:
        uid = os.getuid()
    except (AttributeError, OSError):
        uid = None

    return {
        "schema": 1,
        "platform": {
            "system": platform.system(),
            "sys_platform": sys.platform,
            "machine": platform.machine(),
            "android_api_level": android_api,
            "uid": uid,
        },
        "indicators": {
            "namespace_handles_present": _namespace_inventory(proc),
            "user_namespace_max": max_user_ns,
            "unprivileged_userns_setting": unprivileged_userns,
            "cgroup_v2_controllers": controllers.split() if controllers else [],
            "cgroup_root_writable": os.access(sysfs / "fs" / "cgroup", os.W_OK),
            "seccomp_mode": seccomp,
            "bwrap_path_available": executable_lookup("bwrap"),
            "proot_indicators_present": any(proot_markers),
        },
        "limitations": [
            "Namespace handles do not prove that namespace creation is permitted.",
            "Executable presence does not prove correct sandbox configuration.",
            "This inventory does not test network isolation, mount escape resistance, "
            "resource enforcement, process containment, or secret isolation.",
            "A separate adversarial runtime suite must verify host-side effects.",
        ],
        "result": "diagnostic_only",
        "sandbox_accepted": False,
    }


def main() -> int:
    print(json.dumps(collect_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
