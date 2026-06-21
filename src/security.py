"""
Permission & Approval System for Tool Execution.

Frontier-grade sandboxing and approval controls inspired by Codex CLI
and Claude Code. Implements granular permission policies, command
allowlisting, and interactive approval prompts.
"""

import os
import re
import shlex
from pathlib import Path
from typing import Optional, Set, Tuple, TYPE_CHECKING, Callable
from enum import Enum

if TYPE_CHECKING:
    from src.ui import UIAdapter


class ApprovalPolicy(Enum):
    """Defines when the harness asks for user approval."""
    ALWAYS = "always"           # Ask before every tool execution
    ON_REQUEST = "on-request"   # Ask for dangerous operations only
    NEVER = "never"             # Auto-approve everything (YOLO mode)


class PermissionLevel(Enum):
    """Permission levels for operations."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


# Commands that are safe to run without approval (read-only)
SAFE_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "find", "grep", "rg",
    "tree", "file", "stat", "which", "echo", "pwd", "env",
    "git status", "git log", "git diff", "git branch", "git show",
    "python -m py_compile", "python -c", "node -e",
    "npm list", "pip list", "pip show",
    "test", "type", "readlink", "realpath", "basename", "dirname",
}

# Commands that are always dangerous and require explicit approval
DANGEROUS_PATTERNS = [
    r"^rm\s+(-rf?|--recursive)",
    r"^rm\s+/",
    r"^sudo\s+",
    r"^chmod\s+",
    r"^chown\s+",
    r"^dd\s+",
    r"^mkfs\s+",
    r"^fdisk\s+",
    r"^curl\s+.*\|\s*(bash|sh|zsh|python)",
    r"^wget\s+.*\|\s*(bash|sh|zsh|python)",
    r"^git\s+(push|reset\s+--hard|clean\s+-fd|checkout\s+-f)",
    r"^npm\s+(publish|unpublish|adduser)",
    r"^pip\s+install\s+(?!-e\s+\.)",  # pip install (except editable local)
    r"^docker\s+(rm|rmi|system\s+prune|compose\s+down\s+-v)",
    r"^kill\s+",
    r"^pkill\s+",
    r"^reboot",
    r"^shutdown",
    r"^poweroff",
    r"^>\s+/dev/",   # direct disk writes
    r"^pv",
    r"^dd",
]

# Commands that modify state but are generally safe within a project
MUTATING_COMMANDS = {
    "npm install", "npm run", "npm test", "npm build",
    "pip install -e .", "pip install -r requirements.txt",
    "git add", "git commit", "git checkout", "git stash",
    "mkdir", "touch", "cp", "mv",
    "python", "node", "pytest", "jest",
    "make", "cargo build", "cargo test", "go build", "go test",
}


class Sandbox:
    """Enforces workspace boundaries for file operations."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root.resolve()
        self.writable_roots: Set[Path] = {self.workspace_root}
        self.protected_paths: Set[str] = {".git", ".env"}

    def is_safe_path(self, path: str) -> bool:
        """Check if a path is within the workspace boundary.
        Uses commonpath to prevent prefix-collision attacks
        (e.g., /workspace-extra should not match /workspace).
        Resolves symlinks to prevent TOCTOU race conditions."""
        try:
            from os.path import commonpath
            abs_path = Path(path).resolve()
            resolved_roots = [root.resolve() for root in self.writable_roots]
            for root in resolved_roots:
                if Path(commonpath([str(abs_path), str(root)])) == root:
                    return True
            return False
        except (ValueError, Exception):
            return False

    def is_protected(self, path: str) -> bool:
        """Check if a path contains a protected component (.git, .env, etc.).
        Uses string-based relative path (avoids os.path.relpath FS call)."""
        abs_path = str(Path(path).resolve())
        root = str(self.workspace_root)
        if not abs_path.startswith(root):
            return False
        rel_path = abs_path[len(root):].lstrip(os.sep)
        parts = rel_path.split(os.sep)
        for protected in self.protected_paths:
            if protected in parts:
                return True
        return False

    def validate_write(self, path: str) -> Tuple[bool, str]:
        """Validate a write operation. Returns (allowed, reason)."""
        if not self.is_safe_path(path):
            return False, f"Path '{path}' is outside the workspace boundary."
        if self.is_protected(path):
            return False, f"Path '{path}' is protected (read-only)."
        return True, "OK"


class PermissionManager:
    """Manages approval policies and permission checks."""

    def __init__(
        self,
        workspace_root: Path,
        policy: ApprovalPolicy = ApprovalPolicy.ON_REQUEST,
        ui_adapter: Optional['UIAdapter'] = None,
    ):
        self.sandbox = Sandbox(workspace_root)
        self.policy = policy
        self.always_allow: Set[str] = set()  # Commands user said "always" to
        self.session_denials: Set[str] = set()
        self.ui_adapter = ui_adapter

    def classify_command(self, cmd: str) -> PermissionLevel:
        """Classify a shell command's risk level."""
        cmd_stripped = cmd.strip()

        # Check if user has permanently allowed this command
        if cmd_stripped in self.always_allow:
            return PermissionLevel.ALLOW

        # Check against dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.match(pattern, cmd_stripped):
                return PermissionLevel.ASK if self.policy != ApprovalPolicy.NEVER else PermissionLevel.ALLOW

        # Check if it's a known safe command
        for safe_cmd in SAFE_COMMANDS:
            if cmd_stripped.startswith(safe_cmd):
                return PermissionLevel.ALLOW

        # Check if it's a known mutating but project-safe command
        for mut_cmd in MUTATING_COMMANDS:
            if cmd_stripped.startswith(mut_cmd):
                if self.policy == ApprovalPolicy.ALWAYS:
                    return PermissionLevel.ASK
                return PermissionLevel.ALLOW

        # Unknown commands: depends on policy
        if self.policy == ApprovalPolicy.NEVER:
            return PermissionLevel.ALLOW
        elif self.policy == ApprovalPolicy.ALWAYS:
            return PermissionLevel.ASK
        else:
            # ON_REQUEST: ask for unknown commands
            return PermissionLevel.ASK

    def classify_write(self, filepath: str) -> PermissionLevel:
        """Classify a file write operation's risk level."""
        allowed, reason = self.sandbox.validate_write(filepath)
        if not allowed:
            return PermissionLevel.DENY
        if self.policy == ApprovalPolicy.ALWAYS:
            return PermissionLevel.ASK
        return PermissionLevel.ALLOW

    async def request_approval(self, action_description: str) -> str:
        """
        Request user approval for an action.

        Returns: 'y' (yes), 'n' (no), or 'a' (always allow)
        """
        # Use UIAdapter if available (non-blocking async path)
        if self.ui_adapter is not None:
            approved = await self.ui_adapter.request_approval(action_description)
            return "y" if approved else "n"

        # Fallback: synchronous prompt_toolkit prompt
        from prompt_toolkit import prompt as pt_prompt

        print(f"\n{'─' * 50}")
        print(f"  🔒 APPROVAL REQUIRED")
        print(f"{'─' * 50}")
        print(f"  Action: {action_description}")
        print(f"{'─' * 50}")

        try:
            response = pt_prompt(
                "  Allow? [Y]es / [N]o / [A]lways: ",
                mouse_support=False,
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "n"

        if response in ("y", "yes", ""):
            return "y"
        elif response in ("a", "always"):
            return "a"
        else:
            return "n"
