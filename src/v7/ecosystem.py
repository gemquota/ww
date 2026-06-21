"""V7-17: Ecosystem & Community — contributor onboarding, governance, health (Elena Morales)."""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path


class ContributorOnboarding:
    """Track contributor onboarding pipeline."""

    def __init__(self):
        self._contributors: List[Dict] = []

    def onboard(self, username: str, source: str = "github"):
        self._contributors.append({
            "username": username, "source": source,
            "onboarded_at": datetime.now().isoformat(),
            "first_pr": None, "first_merged_pr": None,
            "active": True,
        })

    def record_first_pr(self, username: str) -> bool:
        for c in self._contributors:
            if c["username"] == username and c["first_pr"] is None:
                c["first_pr"] = datetime.now().isoformat()
                return True
        return False

    def get_health_metrics(self) -> Dict:
        total = len(self._contributors)
        with_pr = sum(1 for c in self._contributors if c["first_pr"] is not None)
        return {
            "total_contributors": total,
            "with_first_pr": with_pr,
            "conversion_rate": round(with_pr / max(total, 1) * 100, 1),
        }


class ReleaseCadence:
    """Track release cadence and schedule."""

    def __init__(self):
        self._releases: List[Dict] = []

    def record_release(self, version: str, features: List[str]):
        self._releases.append({
            "version": version, "features": features,
            "released_at": datetime.now().isoformat(),
        })

    def get_cadence(self) -> Dict:
        if len(self._releases) < 2:
            return {"total_releases": len(self._releases), "avg_days_between": 0}
        dates = [datetime.fromisoformat(r["released_at"]) for r in self._releases]
        gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
        return {
            "total_releases": len(self._releases),
            "avg_days_between": round(sum(gaps) / len(gaps), 1),
            "last_release": self._releases[-1]["version"],
        }


class CommunityHealth:
    """Community health metrics."""

    def __init__(self):
        self._metrics: Dict[str, float] = {}

    def record_metric(self, name: str, value: float):
        self._metrics[name] = value

    def get_health_score(self) -> float:
        if not self._metrics:
            return 0.0
        return round(sum(self._metrics.values()) / len(self._metrics), 2)

    def check_files(self, root: Path) -> Dict:
        return {
            "has_contributing": (root / "CONTRIBUTING.md").exists(),
            "has_code_of_conduct": (root / "CODE_OF_CONDUCT.md").exists() or (root / ".github" / "CODE_OF_CONDUCT.md").exists(),
            "has_license": (root / "LICENSE").exists() or (root / "LICENSE.txt").exists(),
        }
