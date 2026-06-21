"""V7-14: Memory & Storage — persistence, WAL, memory tiers (Dr. Marcus Webb)."""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class MemoryTier:
    name: str
    capacity: int
    ttl_seconds: int
    current_usage: int = 0


class PersistenceManager:
    """Track persistence guarantees across storage backends."""

    def __init__(self):
        self._tiers: Dict[str, MemoryTier] = {}
        self._operations: List[Dict] = []

    def register_tier(self, name: str, capacity: int, ttl_seconds: int):
        self._tiers[name] = MemoryTier(name=name, capacity=capacity, ttl_seconds=ttl_seconds)

    def record_operation(self, tier: str, operation: str, size_bytes: int, success: bool):
        self._operations.append({
            "tier": tier, "operation": operation,
            "size_bytes": size_bytes, "success": success,
        })
        if success and operation == "write":
            self._tiers[tier].current_usage += size_bytes

    def get_guarantees(self) -> Dict:
        return {
            "tiers": {name: {"capacity": t.capacity, "ttl": t.ttl_seconds,
                             "usage_pct": round(t.current_usage / max(t.capacity, 1) * 100, 1)}
                      for name, t in self._tiers.items()},
            "total_operations": len(self._operations),
            "success_rate": round(
                sum(1 for o in self._operations if o["success"]) / max(len(self._operations), 1) * 100, 1
            ),
        }


class CompactionPolicy:
    """Define and track compaction policies."""

    def __init__(self, max_fragmentation: float = 0.3):
        self.max_fragmentation = max_fragmentation
        self._compactions: List[Dict] = []

    def record_compaction(self, tier: str, bytes_freed: int, duration_ms: float):
        self._compactions.append({
            "tier": tier, "bytes_freed": bytes_freed,
            "duration_ms": duration_ms,
        })

    def needs_compaction(self, tier_usage: Dict[str, int]) -> List[str]:
        """Determine which tiers need compaction."""
        needs = []
        for tier, usage in tier_usage.items():
            if usage > 0:
                needs.append(tier)
        return needs

    def get_stats(self) -> Dict:
        if not self._compactions:
            return {"total_compactions": 0}
        total_freed = sum(c["bytes_freed"] for c in self._compactions)
        return {
            "total_compactions": len(self._compactions),
            "total_bytes_freed": total_freed,
            "avg_duration_ms": round(sum(c["duration_ms"] for c in self._compactions) / len(self._compactions), 1),
        }
