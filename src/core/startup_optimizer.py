"""Startup time optimization and hot-path profiling."""
import time
import importlib
from typing import Dict, List, Tuple
from collections import OrderedDict


class StartupProfiler:
    """Profiles module import times to identify startup bottlenecks."""

    def __init__(self):
        self._timings: Dict[str, float] = {}

    def profile_import(self, module_name: str) -> float:
        """Time how long a module takes to import. Returns seconds."""
        start = time.perf_counter()
        importlib.import_module(module_name)
        elapsed = time.perf_counter() - start
        self._timings[module_name] = elapsed
        return elapsed

    def profile_multiple(self, modules: List[str]) -> Dict[str, float]:
        """Profile multiple module imports."""
        for mod in modules:
            self.profile_import(mod)
        return self._timings

    def get_slowest(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get the n slowest imports."""
        sorted_items = sorted(self._timings.items(), key=lambda x: -x[1])
        return sorted_items[:n]

    def report(self) -> str:
        """Generate a startup profiling report."""
        lines = ["Startup Profile Report:", "-" * 50]
        for module, elapsed in sorted(self._timings.items(), key=lambda x: -x[1]):
            bar = "█" * int(elapsed * 100)
            lines.append(f"  {elapsed:>6.3f}s {bar} {module}")
        return "\n".join(lines)


class LazyImporter:
    """Defers module imports until first use to reduce startup time."""

    def __init__(self):
        self._loaded: Dict[str, object] = {}

    def load(self, module_name: str) -> object:
        """Import a module on first call, return cached on subsequent calls."""
        if module_name not in self._loaded:
            self._loaded[module_name] = importlib.import_module(module_name)
        return self._loaded[module_name]

    def is_loaded(self, module_name: str) -> bool:
        return module_name in self._loaded


class HotPathOptimizer:
    """Identifies and optimizes hot code paths."""

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, float] = {}

    def track(self, label: str):
        """Context manager-compatible tracking."""
        return _HotPathContext(self, label)

    def get_hot_paths(self, threshold: int = 100) -> List[Tuple[str, int, float]]:
        """Get paths called more than threshold times, sorted by total time."""
        result = []
        for label in self._counters:
            if self._counters[label] >= threshold:
                total_time = self._timers.get(label, 0)
                result.append((label, self._counters[label], total_time))
        return sorted(result, key=lambda x: -x[2])


class _HotPathContext:
    def __init__(self, optimizer: HotPathOptimizer, label: str):
        self.optimizer = optimizer
        self.label = label
        self.start: float = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = time.perf_counter() - self.start
        self.optimizer._counters[self.label] = self.optimizer._counters.get(self.label, 0) + 1
        self.optimizer._timers[self.label] = self.optimizer._timers.get(self.label, 0) + elapsed
