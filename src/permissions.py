"""Workspace-aware permission policy for WW tool execution.

The default on-request policy allows ordinary project work while prompting for
commands with destructive or system-wide effects. Explicit hard-deny patterns
remain blocked under every policy.
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path


class ApprovalPolicy(str, Enum):
    ALWAYS = "always"
    ON_REQUEST = "on-request"
    NEVER = "never"


class PermissionLevel(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Sandbox:
    """Resolve paths and enforce a single workspace boundary."""

    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root).expanduser().resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        return candidate.resolve()

    def allows(self, path: str | Path) -> bool:
        try:
            self.resolve(path).relative_to(self.workspace_root)
            return True
        except (ValueError, OSError):
            return False


class PermissionManager:
    """Classify file writes and shell commands against the selected policy."""

    _HARD_DENY = (
        re.compile(r"(^|[;&|]\s*)rm\s+(?:(?=[^\s]*r)(?=[^\s]*f)[^\s]+|--recursive\s+--force|--force\s+--recursive)\s+(/|/\*|~)(\s|$)", re.I),
        re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b", re.I),
        re.compile(r"\bwipefs\b", re.I),
        re.compile(r"\bdd\b[^\n]*\bof=/dev/", re.I),
        re.compile(r"\b(shutdown|reboot|poweroff|halt)\b", re.I),
        re.compile(r":\s*\(\s*\)\s*\{[^}]*\}\s*;\s*:", re.I),
    )
    _ASK_PATTERNS = (
        re.compile(r"(^|[;&|]\s*)rm\s", re.I),
        re.compile(r"(^|[;&|]\s*)mv\s", re.I),
        re.compile(r"\bgit\s+reset\s+--hard\b", re.I),
        re.compile(r"\bgit\s+clean\s+-[a-z]*f", re.I),
        re.compile(r"\bgit\s+push\b[^\n]*--force", re.I),
        re.compile(r"\b(sudo|su)\b", re.I),
        re.compile(r"\b(chmod|chown)\b", re.I),
        re.compile(r"\b(pkg|apt|apt-get|pip|pip3|npm|pnpm|yarn)\s+(remove|uninstall)\b", re.I),
        re.compile(r"\b(curl|wget)\b[^\n]*\|\s*(sh|bash)", re.I),
        re.compile(r"\b(killall|pkill)\b", re.I),
    )
    _PROTECTED_NAMES = {
        ".env", ".env.local", ".env.production", ".npmrc",
        "credentials", "secrets", "id_rsa", "id_ed25519",
    }
    _PROTECTED_PARTS = {
        ".git", ".ssh", ".aws", ".gnupg",
    }
    _PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}

    def __init__(
        self,
        workspace_root: str | Path,
        policy: ApprovalPolicy = ApprovalPolicy.ON_REQUEST,
    ):
        self.sandbox = Sandbox(workspace_root)
        self.workspace_root = self.sandbox.workspace_root
        self.policy = policy if isinstance(policy, ApprovalPolicy) else ApprovalPolicy(policy)
        self.always_allow: set[str] = set()

    def classify_write(self, file_path: str) -> PermissionLevel:
        path = self.sandbox.resolve(file_path)
        if not self.sandbox.allows(path):
            return PermissionLevel.DENY

        lowered_parts = {part.lower() for part in path.parts}
        name = path.name.lower()
        if (
            name in self._PROTECTED_NAMES
            or name.startswith(".env.")
            or any(part in self._PROTECTED_PARTS for part in lowered_parts)
            or path.suffix.lower() in self._PROTECTED_SUFFIXES
        ):
            return PermissionLevel.DENY

        if self.policy is ApprovalPolicy.ALWAYS:
            return PermissionLevel.ASK
        return PermissionLevel.ALLOW

    def classify_command(self, command: str) -> PermissionLevel:
        command = (command or "").strip()
        if not command or len(command) > 2000:
            return PermissionLevel.DENY
        if any(pattern.search(command) for pattern in self._HARD_DENY):
            return PermissionLevel.DENY
        if command in self.always_allow:
            return PermissionLevel.ALLOW
        if self.policy is ApprovalPolicy.ALWAYS:
            return PermissionLevel.ASK
        if self.policy is ApprovalPolicy.NEVER:
            return PermissionLevel.ALLOW
        if any(pattern.search(command) for pattern in self._ASK_PATTERNS):
            return PermissionLevel.ASK
        return PermissionLevel.ALLOW
