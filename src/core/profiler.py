"""Performance profiling with flame graph output support."""
import cProfile
import pstats
import io
import time
import functools
from pathlib import Path
from typing import Optional, Callable


class FlameGraphProfiler:
    """Profiler that can output cProfile stats for flame graph generation."""

    def __init__(self, data_dir: str = ".tel"):
        self.data_dir = Path.cwd() / data_dir / "profiles"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiler: Optional[cProfile.Profile] = None
        self._active = False

    def start(self):
        """Start profiling."""
        self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._active = True

    def stop(self) -> str:
        """Stop profiling and save results. Returns path to stats file."""
        if not self._active or not self._profiler:
            return ""
        self._profiler.disable()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        stats_path = self.data_dir / f"profile_{timestamp}.stats"
        self._profiler.dump_stats(str(stats_path))

        # Also save human-readable summary
        s = io.StringIO()
        ps = pstats.Stats(self._profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(30)
        summary_path = self.data_dir / f"profile_{timestamp}.txt"
        summary_path.write_text(s.getvalue())

        self._profiler = None
        self._active = False
        return str(stats_path)

    def get_recent_profiles(self, n: int = 5) -> list:
        """List most recent profile files."""
        files = sorted(self.data_dir.glob("*.stats"), key=lambda f: f.stat().st_mtime, reverse=True)
        return [str(f) for f in files[:n]]

    @staticmethod
    def profile(func: Callable) -> Callable:
        """Decorator to profile a specific function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()
            try:
                return func(*args, **kwargs)
            finally:
                profiler.disable()
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                ps.print_stats(20)
                # Log to debug output
                print(f"[profile] {func.__name__}:")
                print(s.getvalue()[:500])
        return wrapper


class HotPathDetector:
    """Detects hot paths by measuring execution time of key functions."""

    def __init__(self):
        self._timings: dict = {}

    def time(self, label: str) -> callable:
        """Context manager to time a block."""
        return _Timer(self, label)

    def report(self, top_n: int = 10) -> str:
        """Generate a hot path report sorted by total time."""
        sorted_items = sorted(self._timings.items(), key=lambda x: -x[1]["total"])
        lines = ["Hot Path Report:", "-" * 60]
        lines.append(f"{'Function':<40} {'Calls':>6} {'Total (s)':>10} {'Avg (ms)':>10}")
        lines.append("-" * 60)
        for label, data in sorted_items[:top_n]:
            avg_ms = (data["total"] / data["calls"]) * 1000 if data["calls"] > 0 else 0
            lines.append(f"{label:<40} {data['calls']:>6} {data['total']:>10.3f} {avg_ms:>10.2f}")
        return "\n".join(lines)


class _Timer:
    def __init__(self, detector: HotPathDetector, label: str):
        self.detector = detector
        self.label = label
        self.start: float = 0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        elapsed = time.perf_counter() - self.start
        if self.label not in self.detector._timings:
            self.detector._timings[self.label] = {"total": 0.0, "calls": 0}
        self.detector._timings[self.label]["total"] += elapsed
        self.detector._timings[self.label]["calls"] += 1
