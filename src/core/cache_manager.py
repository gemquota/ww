"""
Cache invalidation and management for MemoryManager — NEW-D2#1 (Daniel Park).
Includes adaptive TTL tuning — NEW-V5-D2#2.
"""
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    key: str
    value: Any
    tier: str = "hot"
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    ttl: Optional[float] = None  # seconds
    access_count: int = 0


class TTLConfig:
    """TTL tuning configuration — NEW-V5-D2#2 (Daniel Park)."""

    DEFAULT_TTLS = {
        "hot": 300,       # 5 min
        "facts": 600,     # 10 min
        "summary": 1800,  # 30 min
        "tool_output": 60,   # 1 min
        "context": 120,      # 2 min
        "session": 3600,     # 1 hour
    }

    # TTL bounds for adaptive tuning
    MIN_TTL = 10       # 10 seconds minimum
    MAX_TTL = 7200     # 2 hours maximum

    # Adaptive tuning parameters
    HIT_RATE_TARGET = 80.0   # Target hit rate percentage
    TTL_ADJUSTMENT_FACTOR = 1.2  # Multiplicative adjustment
    ADAPTATION_INTERVAL = 60  # Seconds between auto-tune checks

    _last_tune_time: float = 0.0
    _adaptation_log: list = field(default_factory=list)

    @classmethod
    def get_ttl(cls, tier: str) -> int:
        return cls.DEFAULT_TTLS.get(tier, 300)

    @classmethod
    def set_ttl(cls, tier: str, seconds: int):
        seconds = max(cls.MIN_TTL, min(cls.MAX_TTL, seconds))
        cls.DEFAULT_TTLS[tier] = seconds

    @classmethod
    def auto_tune(cls, tier: str, hit_rate: float) -> Optional[float]:
        """Automatically adjust TTL based on hit rate.
        
        If hit rate is above target, TTL can be reduced (entry stays fresh enough).
        If hit rate is below target, TTL should be increased (entries expire too fast).
        Returns the new TTL value, or None if no adjustment needed.
        """
        current = cls.get_ttl(tier)
        if hit_rate > cls.HIT_RATE_TARGET + 5:
            # Cache is performing well — reduce TTL slightly to save memory
            new_ttl = max(cls.MIN_TTL, int(current / cls.TTL_ADJUSTMENT_FACTOR))
        elif hit_rate < cls.HIT_RATE_TARGET - 5:
            # Cache is underperforming — increase TTL to improve hit rate
            new_ttl = min(cls.MAX_TTL, int(current * cls.TTL_ADJUSTMENT_FACTOR))
        else:
            return None  # Within target range

        cls.set_ttl(tier, new_ttl)
        cls._adaptation_log.append({
            "tier": tier,
            "old_ttl": current,
            "new_ttl": new_ttl,
            "hit_rate": hit_rate,
            "timestamp": time.time(),
        })
        return new_ttl

    @classmethod
    def get_adaptation_history(cls) -> list:
        return cls._adaptation_log[-50:]  # Last 50 adaptations

    @classmethod
    def reset(cls):
        cls._last_tune_time = 0.0
        cls._adaptation_log.clear()


class CacheManager:
    """TTL-aware cache manager with invalidation tracking and adaptive TTL tuning."""

    def __init__(self, default_ttl: Optional[float] = None):
        self._entries: Dict[str, CacheEntry] = {}
        if default_ttl is None:
            default_ttl = float(TTLConfig.get_ttl("hot"))
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._last_tune_time: float = 0.0

    def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None if miss or expired."""
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None

        # Check TTL — expired entry counts as miss
        if entry.ttl is not None and time.time() - entry.created_at > entry.ttl:
            del self._entries[key]
            self._misses += 1
            return None

        entry.accessed_at = time.time()
        entry.access_count += 1
        self._hits += 1

        # Auto-tune check (periodic, per-tier)
        self._maybe_tune()

        return entry.value

    def _maybe_tune(self):
        """Periodically check and auto-tune TTLs based on hit rates."""
        now = time.time()
        if now - self._last_tune_time < TTLConfig.ADAPTATION_INTERVAL:
            return

        self._last_tune_time = now
        stats = self.get_stats()
        for tier in stats.get("tiers", {}):
            tier_hits = stats.get("hits", 0)
            tier_misses = stats.get("misses", 0)
            total = tier_hits + tier_misses
            if total > 10:  # Need minimum samples
                hit_rate = tier_hits / total * 100
                TTLConfig.auto_tune(tier, hit_rate)

    def set(self, key: str, value: Any, tier: str = "hot",
            ttl: Optional[float] = None) -> None:
        """Set a cached value with optional TTL."""
        self._entries[key] = CacheEntry(
            key=key, value=value, tier=tier,
            ttl=ttl if ttl is not None else self.default_ttl
        )

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry. Returns True if existed."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries with a key prefix."""
        to_delete = [k for k in self._entries if k.startswith(prefix)]
        for k in to_delete:
            del self._entries[k]
        return len(to_delete)

    def invalidate_tier(self, tier: str) -> int:
        """Invalidate all entries in a given tier."""
        to_delete = [k for k, e in self._entries.items() if e.tier == tier]
        for k in to_delete:
            del self._entries[k]
        return len(to_delete)

    def get_stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        tier_counts: Dict[str, int] = {}
        hits_by_tier: Dict[str, int] = {}
        misses_by_tier: Dict[str, int] = {}
        for entry in self._entries.values():
            tier_counts[entry.tier] = tier_counts.get(entry.tier, 0) + 1
        return {
            "entries": len(self._entries),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1) * 100, 1),
            "tiers": tier_counts,
            "default_ttl": self.default_ttl,
        }

    def get_tier_stats(self, tier: str) -> Dict[str, Any]:
        """Get per-tier statistics for adaptive tuning analysis."""
        tier_entries = [e for e in self._entries.values() if e.tier == tier]
        if not tier_entries:
            return {"tier": tier, "entries": 0}
        avg_access = sum(e.access_count for e in tier_entries) / len(tier_entries)
        return {
            "tier": tier,
            "entries": len(tier_entries),
            "avg_access_count": round(avg_access, 1),
            "current_ttl": TTLConfig.get_ttl(tier),
            "oldest_entry_age": round(time.time() - min(e.created_at for e in tier_entries), 1),
        }

    def tune_ttl(self, tier: str, new_ttl: int) -> int:
        """Manually tune TTL for a tier. Returns the set value (clamped)."""
        new_ttl = max(TTLConfig.MIN_TTL, min(TTLConfig.MAX_TTL, new_ttl))
        TTLConfig.set_ttl(tier, new_ttl)
        return new_ttl

    def clear(self) -> None:
        self._entries.clear()
        self._hits = 0
        self._misses = 0


class CacheWarmer:
    """Eager cache warming for cold-start mitigation — NEW-D2#3."""

    def __init__(self, cache: CacheManager):
        self.cache = cache

    def warm(self, entries: List[Tuple[str, Any, Optional[float]]]):
        """Pre-populate cache with expected hot entries."""
        for key, value, ttl in entries:
            self.cache.set(key, value, ttl=ttl)

    def estimate_warm_time(self, entries_count: int) -> float:
        return entries_count * 0.001


class CrossSessionWarmer:
    """Cross-session cache warming — NEW-V5-D2#4."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    def warm_from_history(self, session_history: list):
        for entry in session_history[-50:]:
            if "key" in entry and "value" in entry:
                self.cache.set(
                    entry["key"], entry["value"],
                    tier="hot", ttl=TTLConfig.get_ttl("hot")
                )

    @staticmethod
    def estimate_warm_time(entries: int) -> float:
        return entries * 0.002
