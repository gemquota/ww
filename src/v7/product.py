"""V7-15: Product strategy — prioritization, segmentation, adoption (Sofia Reyes)."""
from typing import Dict, List, Any, Optional


class FeaturePrioritization:
    """Framework for feature prioritization scoring."""

    def __init__(self):
        self._features: List[Dict] = []

    def register_feature(self, name: str, description: str,
                         user_impact: int = 5, effort: int = 5, confidence: float = 0.5):
        score = round((user_impact * confidence) / max(effort, 1), 2)
        self._features.append({
            "name": name, "description": description,
            "user_impact": user_impact, "effort": effort,
            "confidence": confidence, "priority_score": score,
        })

    def get_prioritized(self) -> List[Dict]:
        return sorted(self._features, key=lambda x: -x["priority_score"])

    def get_roadmap(self) -> Dict:
        prioritized = self.get_prioritized()
        return {
            "total_features": len(self._features),
            "now": [f for f in prioritized if f["priority_score"] >= 4][:3],
            "next": [f for f in prioritized if 2 <= f["priority_score"] < 4][:5],
            "later": [f for f in prioritized if f["priority_score"] < 2],
        }


class AdoptionMetrics:
    """Track product adoption metrics."""

    def __init__(self):
        self._events: List[Dict] = []

    def record_event(self, event: str, user_id: str, metadata: Dict = None):
        self._events.append({
            "event": event, "user_id": user_id,
            "metadata": metadata or {},
        })

    def get_activation_rate(self) -> float:
        """Percentage of users who performed a key action."""
        unique_users = set(e["user_id"] for e in self._events)
        activated = set(e["user_id"] for e in self._events if e["event"] in ["first_query", "tool_exec"])
        if not unique_users:
            return 0.0
        return round(len(activated) / len(unique_users) * 100, 1)

    def get_retention(self, days: int = 7) -> float:
        """Calculate user retention over N days."""
        return 0.0  # Placeholder — requires timestamp tracking


class CompetitivePositioning:
    """Track competitive positioning analysis."""

    def __init__(self):
        self._comparisons: Dict[str, Dict] = {}

    def add_comparison(self, competitor: str, strength: str, weakness: str, differentiator: str):
        self._comparisons[competitor] = {
            "strength": strength, "weakness": weakness,
            "differentiator": differentiator,
        }

    def get_analysis(self) -> Dict:
        return {
            "competitors_tracked": len(self._comparisons),
            "landscape": self._comparisons,
        }
