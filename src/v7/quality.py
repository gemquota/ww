"""V7-03: Technical debt governance & code quality (Ravi Menon)."""
import ast
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class TechDebtTracker:
    """Track and manage technical debt items across the codebase."""

    def __init__(self, db_path: Path = Path(".tel") / "tech_debt.json"):
        self.db_path = db_path
        self._items: List[Dict] = []
        self._load()

    def _load(self):
        if self.db_path.exists():
            self._items = json.loads(self.db_path.read_text())

    def _save(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(self._items, indent=2))

    def register(self, category: str, description: str,
                 severity: str = "medium", file_path: str = "",
                 line: int = 0) -> Dict:
        """Register a new tech debt item."""
        item = {
            "id": len(self._items) + 1,
            "category": category,
            "description": description,
            "severity": severity,
            "file_path": file_path,
            "line": line,
            "created_at": datetime.now().isoformat(),
            "resolved": False,
            "resolved_at": None,
        }
        self._items.append(item)
        self._save()
        return item

    def resolve(self, item_id: int) -> bool:
        """Mark a tech debt item as resolved."""
        for item in self._items:
            if item["id"] == item_id:
                item["resolved"] = True
                item["resolved_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def get_unresolved(self) -> List[Dict]:
        return [i for i in self._items if not i["resolved"]]

    def summary(self) -> Dict[str, Any]:
        unresolved = self.get_unresolved()
        return {
            "total": len(self._items),
            "unresolved": len(unresolved),
            "resolved": len(self._items) - len(unresolved),
            "by_severity": {
                "high": sum(1 for i in unresolved if i["severity"] == "high"),
                "medium": sum(1 for i in unresolved if i["severity"] == "medium"),
                "low": sum(1 for i in unresolved if i["severity"] == "low"),
            },
            "by_category": self._group_by("category", unresolved),
        }

    def _group_by(self, key: str, items: List[Dict]) -> Dict:
        result: Dict[str, int] = {}
        for item in items:
            val = item.get(key, "unknown")
            result[val] = result.get(val, 0) + 1
        return result

    def scan_codebase_for_debt(self, root: Path) -> List[Dict]:
        """Scan the codebase for common tech debt indicators."""
        found = []
        for pyfile in sorted(root.rglob("src/**/*.py")):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            lines = content.split("\n")

            # Check for long functions (>50 lines)
            for i, line in enumerate(lines, 1):
                if "def " in line and i > 1:
                    func_lines = 0
                    for j in range(i, min(i + 60, len(lines))):
                        if lines[j].startswith("def ") and j > i:
                            break
                        func_lines += 1
                    if func_lines > 50:
                        found.append({
                            "type": "long_function",
                            "file": rel,
                            "line": i,
                            "detail": f"{func_lines} lines (threshold: 50)",
                        })

            # Check for TODO/FIXME without tracking
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("# TODO") or stripped.startswith("# FIXME"):
                    found.append({
                        "type": "untracked_todo",
                        "file": rel,
                        "line": i,
                        "detail": stripped.strip("# "),
                    })

            # Check for wildcard imports
            if "from .* import" in content or "from * import" in content:
                found.append({
                    "type": "wildcard_import",
                    "file": rel,
                    "detail": "Wildcard import detected",
                })

        return found


class CodeReviewMetrics:
    """Track code review cadence and effectiveness."""

    def __init__(self):
        self._reviews: List[Dict] = []

    def record_review(self, pr_id: str, author: str, reviewer: str,
                      lines_changed: int, review_time_hours: float) -> Dict:
        entry = {
            "pr_id": pr_id,
            "author": author,
            "reviewer": reviewer,
            "lines_changed": lines_changed,
            "review_time_hours": review_time_hours,
            "timestamp": datetime.now().isoformat(),
        }
        self._reviews.append(entry)
        return entry

    def average_review_time(self) -> float:
        if not self._reviews:
            return 0.0
        return sum(r["review_time_hours"] for r in self._reviews) / len(self._reviews)

    def review_velocity(self, days: int = 30) -> float:
        recent = [r for r in self._reviews
                  if (datetime.now() - datetime.fromisoformat(r["timestamp"])).days <= days]
        return len(recent) / max(days, 1)
