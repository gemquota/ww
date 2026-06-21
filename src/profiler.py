"""
Simple hot-path profiler with context manager decorator.
Addresses V4-P2 and V2 Performance profiling.
"""
import time
import functools
import os
from typing import Callable, Dict
from loguru import logger


class Profiler:
    """Lightweight profiling for hot-path operations.
    
    Usage:
        @Profiler.profile
        async def hot_path(): ...
        
        # Or as context manager:
        with Profiler("context_build") as p:
            # ... work ...
            p.record(count=len(items))
    """
    _stats: Dict[str, Dict] = {}
    
    @classmethod
    def profile(cls, func: Callable) -> Callable:
        """Decorator that records execution time for a function."""
        name = f"{func.__module__}.{func.__qualname__}"
        if name not in cls._stats:
            cls._stats[name] = {"calls": 0, "total_s": 0.0, "min_s": float('inf'), "max_s": 0.0}
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                cls._record(name, elapsed)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                cls._record(name, elapsed)
        
        import inspect
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper
    
    @classmethod
    def _record(cls, name: str, elapsed: float):
        if name not in cls._stats:
            cls._stats[name] = {"calls": 0, "total_s": 0.0, "min_s": float('inf'), "max_s": 0.0}
        cls._stats[name]["calls"] += 1
        cls._stats[name]["total_s"] += elapsed
        cls._stats[name]["min_s"] = min(cls._stats[name]["min_s"], elapsed)
        cls._stats[name]["max_s"] = max(cls._stats[name]["max_s"], elapsed)
    
    @classmethod
    def report(cls) -> str:
        """Get a formatted profiling report."""
        if not cls._stats:
            return "(no profiling data collected)"
        lines = ["\n=== Profiler Report ===", f"{'Function':<50} {'Calls':>6} {'Total(s)':>10} {'Avg(s)':>10} {'Min(s)':>10} {'Max(s)':>10}"]
        lines.append("-" * 96)
        for name in sorted(cls._stats):
            s = cls._stats[name]
            avg = s["total_s"] / s["calls"] if s["calls"] else 0
            lines.append(f"{name:<50} {s['calls']:>6} {s['total_s']:>10.4f} {avg:>10.4f} {s['min_s']:>10.4f} {s['max_s']:>10.4f}")
        return "\n".join(lines)
    
    @classmethod
    def reset(cls):
        cls._stats.clear()
    
    def __init__(self, name: str = "profile"):
        self.name = name
        self.start = 0.0
        self._extra = {}
    
    def __enter__(self):
        self.start = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        elapsed = time.perf_counter() - self.start
        self._record(self.name, elapsed)
    
    def record(self, **kwargs):
        self._extra.update(kwargs)
