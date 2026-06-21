"""
Post-generation quality pipeline for code generation.
Addresses NEW-E1#1 (Dr. Felix Weber) and NEW-E3#1 (Amir Hassan).
"""
import subprocess
import sys
from typing import List, Tuple, Optional
from pathlib import Path


class PostGenerationPipeline:
    """Runs quality checks on generated code before finalizing."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def syntax_check(self, filepath: Path) -> Tuple[bool, str]:
        """Run py_compile syntax check on a Python file."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(filepath)],
                capture_output=True, text=True,
                cwd=self.workspace_root,
            )
            if result.returncode == 0:
                return True, "Syntax OK"
            return False, result.stderr or result.stdout
        except Exception as e:
            return False, str(e)

    def lint_check(self, filepath: Path) -> Tuple[bool, str]:
        """Run ruff lint check on a file."""
        try:
            result = subprocess.run(
                ["ruff", "check", "--quiet", str(filepath)],
                capture_output=True, text=True,
                cwd=self.workspace_root,
            )
            if result.returncode == 0:
                return True, "Lint OK"
            return False, result.stdout or result.stderr or "Lint failed"
        except FileNotFoundError:
            return True, "ruff not installed, skipping"
        except Exception as e:
            return False, str(e)

    def format_check(self, filepath: Path) -> Tuple[bool, str]:
        """Check and auto-fix formatting with ruff."""
        try:
            result = subprocess.run(
                ["ruff", "format", "--check", str(filepath)],
                capture_output=True, text=True,
                cwd=self.workspace_root,
            )
            if result.returncode == 0:
                return True, "Format OK"
            # Try auto-fix
            subprocess.run(
                ["ruff", "format", str(filepath)],
                capture_output=True, text=True,
                cwd=self.workspace_root,
            )
            return False, "Auto-formatted"
        except FileNotFoundError:
            return True, "ruff not installed, skipping"
        except Exception as e:
            return False, str(e)

    def run_all(self, filepath: Path) -> List[dict]:
        """Run all quality checks on a file."""
        results = []
        for name, check_fn in [
            ("syntax", self.syntax_check),
            ("lint", self.lint_check),
            ("format", self.format_check),
        ]:
            passed, msg = check_fn(filepath)
            results.append({
                "check": name,
                "passed": passed,
                "message": msg,
            })
        return results

    def is_approved(self, results: List[dict]) -> bool:
        """Check if all critical checks passed."""
        for r in results:
            if r["check"] == "syntax" and not r["passed"]:
                return False
        return True
