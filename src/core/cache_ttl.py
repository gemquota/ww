"""Configurable cache TTL management with adaptive tuning."""
import time
from typing import Dict, Optional, Any, Callable
from collections import OrderedDict


class TTLEntry:
    def __init__(self, key: str, value: Any, ttl: float, created_at: float = None):
        self.key = key
        self.value = value
        self.ttl = ttl
        self.created_at = created_at or time.time()
        self.access_count = 0
        self.last_accessed = self.created_at

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    def access(self):
        self.access_count += 1
        self.last_accessed = time.time()


class AdaptiveCache:
    """Cache with per-key TTL and adaptive eviction based on access patterns."""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000):
        self._store: Dict[str, TTLEntry] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return default
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return default
        entry.access()
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        if len(self._store) >= self.max_size:
            self._evict_one()
        self._store[key] = TTLEntry(key, value, ttl or self.default_ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def _evict_one(self):
        """Evict the least recently accessed expired or oldest entry."""
        if not self._store:
            return
        # Prefer evicting expired entries
        for key, entry in list(self._store.items()):
            if entry.is_expired():
                del self._store[key]
                self._evictions += 1
                return
        # Evict least recently accessed
        oldest = min(self._store.items(), key=lambda x: x[1].last_accessed)
        del self._store[oldest[0]]
        self._evictions += 1

    def get_stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "evictions": self._evictions,
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
        }

    def get_ttl_for(self, key: str) -> Optional[float]:
        """Get remaining TTL for a key in seconds."""
        entry = self._store.get(key)
        if entry is None:
            return None
        remaining = entry.ttl - (time.time() - entry.created_at)
        return max(0.0, remaining)


class TTLConfig:
    """Centralized TTL configuration with environment-based overrides."""
    
    _ttls = {
        "hot": 300,       # 5 min — recent conversation turns
        "warm": 1800,     # 30 min — session data
        "cold": 7200,     # 2 hours — persisted context
        "session": 3600,  # 1 hour — session cache
        "tool_defs": 600, # 10 min — tool definitions
    }

    @classmethod
    def get_ttl(cls, tier: str) -> float:
        return cls._ttls.get(tier, cls._ttls["hot"])

    @classmethod
    def set_ttl(cls, tier: str, ttl: float):
        cls._ttls[tier] = ttl

    @classmethod
    def configure(cls, overrides: Dict[str, float]):
        cls._ttls.update(overrides)
