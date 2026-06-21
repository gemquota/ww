"""
Backpressure and resource fairness system.
Addresses NEW-B2#2, NEW-B2#3 (Dr. Aisha Bakari).
"""
import time
from typing import Dict, Optional
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ResourceQuota:
    max_concurrent: int = 5
    max_per_second: int = 10
    max_burst: int = 3


class BackpressureManager:
    """Manages backpressure and fairness across resource types."""

    def __init__(self):
        self.quotas: Dict[str, ResourceQuota] = defaultdict(ResourceQuota)
        self._usage: Dict[str, list] = defaultdict(list)  # resource -> [timestamps]
        self._active: Dict[str, int] = defaultdict(int)  # resource -> count

    def set_quota(self, resource: str, quota: ResourceQuota):
        """Set resource quota for a named resource."""
        self.quotas[resource] = quota

    def acquire(self, resource: str) -> bool:
        """Try to acquire a resource slot. Returns False if throttled."""
        quota = self.quotas[resource]
        now = time.time()

        # Rate limit check
        self._usage[resource] = [t for t in self._usage[resource] if now - t < 1.0]
        if len(self._usage[resource]) >= quota.max_per_second:
            return False

        # Concurrency check
        if self._active[resource] >= quota.max_concurrent:
            return False

        self._usage[resource].append(now)
        self._active[resource] += 1
        return True

    def release(self, resource: str):
        """Release a previously acquired resource slot."""
        self._active[resource] = max(0, self._active[resource] - 1)

    def get_stats(self, resource: str) -> dict:
        """Get current usage stats for a resource."""
        return {
            "active": self._active[resource],
            "recent_per_sec": len([t for t in self._usage[resource] if time.time() - t < 1.0]),
            "quota_max_concurrent": self.quotas[resource].max_concurrent,
            "quota_max_per_second": self.quotas[resource].max_per_second,
        }

    def wait_time(self, resource: str) -> float:
        """Estimate wait time before resource is available."""
        if self.acquire(resource):
            self.release(resource)
            return 0.0
        return 1.0  # Default backoff: 1 second
