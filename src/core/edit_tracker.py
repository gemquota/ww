"""
Edit precision metrics for SEARCH/REPLACE operations — NEW-E1#3 (Dr. Felix Weber).
"""
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path


class EditPrecisionTracker:
    """Track SEARCH/REPLACE precision and user acceptance rates."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_attempt(self, filepath: str, search: str, replace: str,
                    applied: bool, accepted: Optional[bool] = None) -> str:
        """Log a SEARCH/REPLACE attempt."""
        entry = {
            "timestamp": time.time(),
            "filepath": filepath,
            "search_length": len(search),
            "replace_length": len(replace),
            "applied": applied,
            "accepted": accepted,
            "duration_ms": 0.0,
        }

        try:
            history = json.loads(self.log_path.read_text()) if self.log_path.exists() else []
        except (json.JSONDecodeError, FileNotFoundError):
            history = []

        history.append(entry)
        self.log_path.write_text(json.dumps(history, indent=2))
        return f"edit_{len(history)}"

    def get_precision_rate(self) -> Dict[str, float]:
        """Calculate precision and acceptance rates."""
        try:
            history = json.loads(self.log_path.read_text()) if self.log_path.exists() else []
        except (json.JSONDecodeError, FileNotFoundError):
            history = []

        if not history:
            return {"total": 0, "apply_rate": 0.0, "accept_rate": 0.0}

        total = len(history)
        applied = sum(1 for e in history if e.get("applied"))
        accepted = sum(1 for e in history if e.get("accepted") is True)
        rejected = sum(1 for e in history if e.get("accepted") is False)

        return {
            "total": total,
            "applied": applied,
            "accepted": accepted,
            "rejected": rejected,
            "apply_rate": round(applied / total * 100, 1) if total else 0.0,
            "accept_rate": round(accepted / max(applied, 1) * 100, 1) if applied else 0.0,
        }

    def get_precision_trend(self, window: int = 20) -> List[Dict]:
        """Get precision trend over recent edits."""
        try:
            history = json.loads(self.log_path.read_text()) if self.log_path.exists() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

        recent = history[-window:]
        trend = []
        for i, entry in enumerate(recent):
            trend.append({
                "edit_number": i + 1,
                "applied": entry.get("applied", False),
                "accepted": entry.get("accepted"),
            })
        return trend


class PerEditUndo:
    """Per-edit undo tracking within checkpoints — NEW-E1#4."""

    def __init__(self):
        self._edits: List[Dict[str, Any]] = []

    def record_edit(self, filepath: str, original_content: str,
                    new_content: str, edit_id: Optional[str] = None):
        """Record an edit for potential undo."""
        self._edits.append({
            "edit_id": edit_id or f"edit_{len(self._edits)}",
            "filepath": filepath,
            "original_content": original_content,
            "new_content": new_content,
            "timestamp": time.time(),
            "reverted": False,
        })

    def undo_last(self) -> Optional[Dict[str, Any]]:
        """Undo the most recent non-reverted edit."""
        for i in range(len(self._edits) - 1, -1, -1):
            if not self._edits[i]["reverted"]:
                edit = self._edits[i]
                edit["reverted"] = True
                return edit
        return None

    def get_recent(self, count: int = 5) -> List[Dict]:
        return self._edits[-count:]
