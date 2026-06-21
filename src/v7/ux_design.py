"""V7-09,10,11: UX Design — terminal UX, HCI, visual design (Amara Osei, Fatima Al-Rashid, Leo Park)."""
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class UXPattern:
    name: str
    description: str
    usage_count: int = 0
    user_satisfaction: float = 0.0


class TerminalUX:
    """Track and analyze terminal UX patterns."""

    def __init__(self):
        self.patterns: List[UXPattern] = []
        self._errors: List[Dict] = []

    def register_pattern(self, name: str, description: str):
        self.patterns.append(UXPattern(name=name, description=description))

    def record_usage(self, pattern_name: str, satisfied: bool = True):
        for p in self.patterns:
            if p.name == pattern_name:
                p.usage_count += 1
                total = (p.usage_count - 1) * p.user_satisfaction + (1.0 if satisfied else 0.0)
                p.user_satisfaction = round(total / p.usage_count, 2)
                return

    def record_error(self, error_type: str, context: str):
        self._errors.append({"type": error_type, "context": context})

    def get_pattern_report(self) -> Dict:
        return {
            "patterns": [{"name": p.name, "usage": p.usage_count, "satisfaction": p.user_satisfaction}
                         for p in self.patterns],
            "total_errors": len(self._errors),
            "top_patterns": sorted(
                [{"name": p.name, "score": p.usage_count * p.user_satisfaction}
                 for p in self.patterns if p.usage_count > 0],
                key=lambda x: -x["score"]
            )[:5],
        }


class TrustCalibrator:
    """Human-agent trust calibration metrics."""

    def __init__(self):
        self._interactions: List[Dict] = []

    def record_interaction(self, action: str, user_approved: bool, response_time_ms: float):
        self._interactions.append({
            "action": action, "user_approved": user_approved,
            "response_time_ms": response_time_ms,
        })

    def get_trust_score(self) -> float:
        if not self._interactions:
            return 1.0
        approval_rate = sum(1 for i in self._interactions if i["user_approved"]) / len(self._interactions)
        speed_score = 1.0 - min(1.0, sum(i["response_time_ms"] for i in self._interactions) / (len(self._interactions) * 5000))
        return round((approval_rate * 0.6 + speed_score * 0.4), 2)


class VisualConsistency:
    """Track visual/theme consistency."""

    def __init__(self):
        self._theme_values: Dict[str, str] = {}

    def set_theme(self, key: str, value: str):
        self._theme_values[key] = value

    def check_consistency(self) -> Dict:
        return {
            "defined_tokens": len(self._theme_values),
            "tokens": dict(self._theme_values),
        }
