"""
Git Checkpoint & State Reversion System.

Frontier-grade undo/checkpoint system inspired by Claude Code and Aider.
Automatically creates lightweight git stashes or patch files before
destructive operations, enabling instant rollback with /undo.
"""

import subprocess
import datetime
import json
from pathlib import Path
from typing import Optional, List, Dict


class CheckpointManager:
    """Manages file state checkpoints for safe undo operations."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.checkpoints_dir = workspace_root / ".ww" / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict] = []
        self._load_history()

    def _load_history(self):
        """Load checkpoint history from disk."""
        history_file = self.checkpoints_dir / "history.json"
        if history_file.exists():
            try:
                self.history = json.loads(history_file.read_text())
            except (json.JSONDecodeError, Exception):
                self.history = []

    def _save_history(self):
        """Persist checkpoint history to disk."""
        history_file = self.checkpoints_dir / "history.json"
        history_file.write_text(json.dumps(self.history, indent=2))

    def _is_git_repo(self) -> bool:
        """Check if workspace is a git repository."""
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _get_git_status(self) -> str:
        """Get current git status (short format)."""
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def create_checkpoint(self, description: str = "") -> Optional[str]:
        """
        Create a checkpoint before a destructive operation.

        Strategy:
        1. If git repo: create a lightweight patch of current state
        2. Also store individual file backups for non-git scenarios
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"cp_{timestamp}_{len(self.history)}"
        checkpoint_path = self.checkpoints_dir / checkpoint_id

        checkpoint_data = {
            "id": checkpoint_id,
            "timestamp": timestamp,
            "description": description,
            "files": {},
            "has_git_patch": False,
        }

        if self._is_git_repo():
            # Create a git diff patch of the working tree
            result = subprocess.run(
                ["git", "diff"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                checkpoint_path.mkdir(parents=True, exist_ok=True)
                patch_file = checkpoint_path / "working_tree.patch"
                patch_file.write_text(result.stdout)
                checkpoint_data["has_git_patch"] = True

            # Also capture untracked files list
            result = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                staged_patch = checkpoint_path / "staged.patch"
                staged_patch.write_text(result.stdout)

        self.history.append(checkpoint_data)
        self._save_history()
        return checkpoint_id

    def save_file_state(self, filepath: Path, checkpoint_id: Optional[str] = None):
        """Save the current state of a specific file before modification."""
        if not filepath.exists():
            return

        if not checkpoint_id and self.history:
            checkpoint_id = self.history[-1]["id"]
        elif not checkpoint_id:
            checkpoint_id = self.create_checkpoint("auto-save")

        checkpoint_path = self.checkpoints_dir / checkpoint_id
        checkpoint_path.mkdir(parents=True, exist_ok=True)

        # Store the file content
        rel_path = filepath.relative_to(self.workspace_root)
        backup_path = checkpoint_path / str(rel_path).replace("/", "__")
        backup_path.write_bytes(filepath.read_bytes())

        # Update history with file info
        for entry in self.history:
            if entry["id"] == checkpoint_id:
                entry["files"][str(rel_path)] = str(backup_path)
                break

        self._save_history()

    def undo(self) -> str:
        """
        Undo the last operation by restoring the previous checkpoint.

        Returns a status message describing what was undone.
        """
        if not self.history:
            return "No checkpoints available to undo."

        checkpoint = self.history.pop()
        checkpoint_path = self.checkpoints_dir / checkpoint["id"]

        restored_files = []

        # Restore individual file backups
        for rel_path, backup_path in checkpoint["files"].items():
            backup = Path(backup_path)
            if backup.exists():
                target = self.workspace_root / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(backup.read_bytes())
                restored_files.append(rel_path)

        # If we have a git patch, we could also use git checkout
        if checkpoint.get("has_git_patch") and self._is_git_repo():
            # Reset any staged changes from this turn
            subprocess.run(
                ["git", "checkout", "--", "."],
                cwd=self.workspace_root,
                capture_output=True,
            )

        # Clean up checkpoint directory
        if checkpoint_path.exists():
            import shutil
            shutil.rmtree(checkpoint_path)

        self._save_history()

        if restored_files:
            file_list = "\n  ".join(restored_files)
            return (
                f"Undone checkpoint '{checkpoint['id']}'.\n"
                f"  Restored {len(restored_files)} file(s):\n  {file_list}"
            )
        else:
            return f"Undone checkpoint '{checkpoint['id']}' (no file changes to restore)."

    def get_history_summary(self) -> str:
        """Get a summary of available checkpoints."""
        if not self.history:
            return "No checkpoints recorded this session."

        lines = ["Checkpoint History:"]
        for i, cp in enumerate(reversed(self.history[-10:])):
            file_count = len(cp["files"])
            lines.append(
                f"  [{i}] {cp['id']} - {cp['description'] or 'auto'} "
                f"({file_count} file{'s' if file_count != 1 else ''})"
            )
        return "\n".join(lines)
