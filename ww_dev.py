#!/usr/bin/env python3
"""WW development runner: compile, test, and exercise the local backend."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IGNORED = {".git", ".venv", "__pycache__", ".old", ".ww", ".tel", "site"}


def run_checks(skip_tests: bool = False) -> int:
    commands = [
        [sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests", "gemini_bridge.py"],
    ]
    if not skip_tests:
        commands.append([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    commands.append([sys.executable, "-m", "scripts.termux_acceptance", "--skip-tests"])

    for command in commands:
        print("\n$", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            print(f"FAILED (exit {result.returncode})", file=sys.stderr)
            return result.returncode
    print("\nWW development checks passed.", flush=True)
    return 0


def snapshot() -> dict[Path, int]:
    state: dict[Path, int] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix not in {".py", ".html", ".yml", ".yaml"}:
            continue
        try:
            state[path] = path.stat().st_mtime_ns
        except OSError:
            continue
    return state


def watch(skip_tests: bool = False) -> int:
    previous = snapshot()
    print("Watching WW source, tests, workflows and frontend. Press Ctrl-C to stop.")
    try:
        while True:
            time.sleep(1)
            current = snapshot()
            if current != previous:
                changed = sorted(
                    str(path.relative_to(ROOT))
                    for path in set(previous) | set(current)
                    if previous.get(path) != current.get(path)
                )
                print("\nChanged:", ", ".join(changed), flush=True)
                previous = current
                result = run_checks(skip_tests=skip_tests)
                if result:
                    print("Checks failed; watching for the next edit.", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped watching.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WW development checks")
    parser.add_argument("--watch", "-w", action="store_true", help="rerun checks when source changes")
    parser.add_argument("--skip-tests", action="store_true", help="skip unittest discovery")
    args = parser.parse_args()
    if args.watch:
        result = run_checks(skip_tests=args.skip_tests)
        if result:
            print("Initial checks failed; entering watch mode.", file=sys.stderr)
        return watch(skip_tests=args.skip_tests)
    return run_checks(skip_tests=args.skip_tests)


if __name__ == "__main__":
    raise SystemExit(main())
