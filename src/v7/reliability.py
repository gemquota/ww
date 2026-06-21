"""V7-07: Reliability — observability, SLI/SLO, incident response (David Park)."""
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class ObservabilityPipeline:
    """Track observability pipeline health."""

    def __init__(self):
        self._events: List[Dict] = []

    def record_event(self, event_type: str, source: str, duration_ms: float, success: bool):
        self._events.append({
            "type": event_type,
            "source": source,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })

    def get_sli(self, event_type: str, window_minutes: int = 60) -> Dict:
        """Calculate Service Level Indicator for a specific event type."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        relevant = [e for e in self._events
                    if e["type"] == event_type
                    and datetime.fromisoformat(e["timestamp"]) > cutoff]
        if not relevant:
            return {"event_type": event_type, "sli": 1.0, "samples": 0}
        successes = sum(1 for e in relevant if e["success"])
        return {
            "event_type": event_type,
            "sli": round(successes / len(relevant), 3),
            "samples": len(relevant),
            "window_minutes": window_minutes,
        }

    def get_latency_p99(self, event_type: str) -> float:
        """Get p99 latency for an event type."""
        relevant = [e["duration_ms"] for e in self._events if e["type"] == event_type]
        if not relevant:
            return 0.0
        relevant.sort()
        idx = int(len(relevant) * 0.99)
        return relevant[idx]


class IncidentResponseTracker:
    """Track incident response metrics."""

    def __init__(self):
        self._incidents: List[Dict] = []

    def record_incident(self, severity: str, description: str, detection_time: float):
        self._incidents.append({
            "id": len(self._incidents) + 1,
            "severity": severity,
            "description": description,
            "detected_at": detection_time,
            "resolved_at": None,
            "mttr_minutes": None,
        })

    def resolve_incident(self, incident_id: int) -> bool:
        for inc in self._incidents:
            if inc["id"] == incident_id and inc["resolved_at"] is None:
                inc["resolved_at"] = time.time()
                inc["mttr_minutes"] = round((inc["resolved_at"] - inc["detected_at"]) / 60, 1)
                return True
        return False

    def get_mttr(self) -> float:
        resolved = [i["mttr_minutes"] for i in self._incidents if i["mttr_minutes"] is not None]
        if not resolved:
            return 0.0
        return round(sum(resolved) / len(resolved), 1)

    def get_open_incidents(self) -> List[Dict]:
        return [i for i in self._incidents if i["resolved_at"] is None]


class ChaosReadiness:
    """Track chaos engineering readiness."""

    @staticmethod
    def check_readiness(root: Path) -> Dict:
        chaos_dir = root / "chaos"
        return {
            "chaos_dir_exists": chaos_dir.exists(),
            "readme_exists": (chaos_dir / "README.md").exists() if chaos_dir.exists() else False,
            "experiments_defined": len(list(chaos_dir.rglob("*.md"))) if chaos_dir.exists() else 0,
        }
