"""V7-02: Distributed Systems — consistency, partitions, consensus (Dr. Victor Stein)."""
from typing import Dict, List, Optional, Any
import time


class ConsistencyModel:
    """Track and analyze consistency model choices."""

    def __init__(self):
        self._operations: List[Dict] = []

    def record_operation(self, op_type: str, key: str, value: Any, consistency: str = "eventual"):
        self._operations.append({
            "type": op_type, "key": key, "value": value,
            "consistency": consistency, "timestamp": time.time(),
        })

    def check_consistency(self, key: str) -> Dict:
        ops = [o for o in self._operations if o["key"] == key]
        if not ops:
            return {"key": key, "status": "no_data"}
        writes = [o for o in ops if o["type"] == "write"]
        reads = [o for o in ops if o["type"] == "read"]
        return {
            "key": key,
            "writes": len(writes),
            "reads": len(reads),
            "models_used": list(set(o["consistency"] for o in ops)),
            "last_write": writes[-1]["value"] if writes else None,
        }


class PartitionHandler:
    """Handle and simulate network partitions."""

    def __init__(self):
        self._partitions: List[Dict] = []

    def simulate_partition(self, duration_seconds: float, affected_services: List[str]):
        self._partitions.append({
            "id": len(self._partitions) + 1,
            "duration": duration_seconds,
            "affected": affected_services,
            "started_at": time.time(),
            "resolved": False,
        })

    def resolve_partition(self, partition_id: int) -> bool:
        for p in self._partitions:
            if p["id"] == partition_id and not p["resolved"]:
                p["resolved"] = True
                p["resolved_at"] = time.time()
                return True
        return False

    def get_active(self) -> List[Dict]:
        return [p for p in self._partitions if not p["resolved"]]


class EventDrivenArchitecture:
    """Event-driven architecture analysis."""

    def __init__(self):
        self._events: List[Dict] = []

    def register_event(self, name: str, source: str, consumers: List[str]):
        self._events.append({
            "name": name, "source": source,
            "consumers": consumers, "registered_at": time.time(),
        })

    def get_publisher_consumer_map(self) -> Dict[str, List[str]]:
        mapping = {}
        for event in self._events:
            mapping[event["name"]] = event["consumers"]
        return mapping

    def find_orphan_events(self) -> List[str]:
        return [e["name"] for e in self._events if not e["consumers"]]
