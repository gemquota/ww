"""V7-12: Security & trust improvements (Aria Thompson)."""
import os
import stat
from pathlib import Path
from typing import List, Dict, Optional


class SecurityAuditor:
    """Audit security posture of the codebase."""

    @staticmethod
    def check_file_permissions(root: Path) -> List[Dict]:
        """Check for overly permissive file permissions."""
        issues = []
        for pyfile in root.rglob("*.py"):
            mode = os.stat(pyfile).st_mode
            if mode & stat.S_IWOTH:
                issues.append({
                    "file": str(pyfile.relative_to(root)),
                    "permissions": oct(mode),
                    "issue": "World-writable file",
                })
        return issues

    @staticmethod
    def check_hardcoded_secrets(root: Path) -> List[Dict]:
        """Scan for potential hardcoded secrets."""
        patterns = [
            "api_key", "apikey", "API_KEY",
            "secret", "SECRET", "password", "PASSWORD",
            "token", "TOKEN", "credential",
        ]
        issues = []
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if any(p in stripped for p in patterns):
                    # Filter out safe patterns
                    if "os.getenv" in stripped or "os.environ" in stripped:
                        continue
                    if '"test"' in stripped.lower() or "'test'" in stripped.lower():
                        continue
                    if line.strip().startswith("#"):
                        continue
                    if "hardcoded" in stripped.lower():
                        continue
                    issues.append({
                        "file": rel,
                        "line": i,
                        "pattern": next(p for p in patterns if p in stripped),
                        "context": stripped[:80],
                    })
        return issues


class TrustBoundaryValidator:
    """Validate trust boundaries between components."""

    @staticmethod
    def check_template_injection_points(root: Path) -> List[Dict]:
        """Find places where user input enters template rendering."""
        issues = []
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "render(" in line and any(w in line for w in ["user_", "input", "query", "prompt"]):
                    issues.append({
                        "file": rel,
                        "line": i,
                        "context": line.strip()[:80],
                        "note": "Template rendering with dynamic input",
                    })
        return issues
