"""V7-08, 18: AI/Agent quality — inference, caching, benchmarking (Dr. Felix Weber / Dr. Nina Sharma)."""
import time
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path


class InferencePipeline:
    """Track inference pipeline efficiency."""

    def __init__(self):
        self._calls: List[Dict] = []

    def record_call(self, model: str, input_tokens: int, output_tokens: int,
                    duration_ms: float, success: bool, cached: bool = False):
        self._calls.append({
            "model": model, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "duration_ms": duration_ms,
            "success": success, "cached": cached,
            "timestamp": time.time(),
        })

    def get_efficiency(self) -> Dict:
        if not self._calls:
            return {"total_calls": 0}
        total_duration = sum(c["duration_ms"] for c in self._calls)
        total_tokens = sum(c["input_tokens"] + c["output_tokens"] for c in self._calls)
        cached = sum(1 for c in self._calls if c["cached"])
        return {
            "total_calls": len(self._calls),
            "avg_duration_ms": round(total_duration / len(self._calls), 1),
            "total_tokens": total_tokens,
            "tokens_per_second": round(total_tokens / max(total_duration / 1000, 0.001), 1),
            "cache_hit_rate": round(cached / len(self._calls) * 100, 1),
            "success_rate": round(sum(1 for c in self._calls if c["success"]) / len(self._calls) * 100, 1),
        }


class PromptCache:
    """Prompt caching layer with TTL."""

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, Dict] = {}
        self.max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if entry and entry["ttl"] > time.time():
            self._hits += 1
            return entry["value"]
        if key in self._cache:
            del self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: str, ttl_seconds: int = 300):
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["created"])
            del self._cache[oldest]
        self._cache[key] = {
            "value": value,
            "ttl": time.time() + ttl_seconds,
            "created": time.time(),
        }

    def stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1) * 100, 1),
            "max_size": self.max_size,
        }


class LatencyBudget:
    """Track latency budgets for agent operations."""

    def __init__(self):
        self._budgets: Dict[str, float] = {}
        self._actuals: Dict[str, List[float]] = {}

    def set_budget(self, operation: str, max_ms: float):
        self._budgets[operation] = max_ms

    def record(self, operation: str, duration_ms: float):
        if operation not in self._actuals:
            self._actuals[operation] = []
        self._actuals[operation].append(duration_ms)

    def check_budget(self, operation: str) -> Dict:
        if operation not in self._budgets:
            return {"operation": operation, "budget_ms": None, "status": "no_budget"}
        if operation not in self._actuals:
            return {"operation": operation, "budget_ms": self._budgets[operation], "status": "no_data"}
        avg = sum(self._actuals[operation]) / len(self._actuals[operation])
        return {
            "operation": operation,
            "budget_ms": self._budgets[operation],
            "actual_avg_ms": round(avg, 1),
            "within_budget": avg <= self._budgets[operation],
            "status": "ok" if avg <= self._budgets[operation] else "over_budget",
        }


class BenchmarkDesign:
    """Design and run evaluation benchmarks."""

    def __init__(self):
        self._benchmarks: List[Dict] = []

    def register(self, name: str, task_fn: Callable, expected_output: Any, tags: List[str] = None):
        self._benchmarks.append({
            "name": name,
            "task_fn": task_fn,
            "expected_output": expected_output,
            "tags": tags or [],
        })

    def run_all(self) -> List[Dict]:
        results = []
        for bm in self._benchmarks:
            start = time.time()
            try:
                output = bm["task_fn"]()
                passed = output == bm["expected_output"]
                results.append({
                    "name": bm["name"],
                    "passed": passed,
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": None,
                })
            except Exception as e:
                results.append({
                    "name": bm["name"],
                    "passed": False,
                    "duration_ms": round((time.time() - start) * 1000, 1),
                    "error": str(e),
                })
        return results

    def summary(self) -> Dict:
        results = self.run_all()
        passed = sum(1 for r in results if r["passed"])
        return {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "pass_rate": round(passed / max(len(results), 1) * 100, 1),
        }
