"""Memory allocation auditing and leak detection."""
import tracemalloc
import gc
import sys
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class MemoryAllocationAuditor:
    """Audits memory allocations to identify hot spots and potential leaks."""

    def __init__(self):
        self._snapshots: List = []
        self._tracking = False

    def start_tracking(self):
        """Begin tracking memory allocations."""
        tracemalloc.start()
        self._tracking = True
        self._snapshots = [tracemalloc.take_snapshot()]

    def snapshot(self) -> int:
        """Take a memory snapshot. Returns current memory usage in bytes."""
        if not self._tracking:
            return 0
        self._snapshots.append(tracemalloc.take_snapshot())
        return self._get_current_memory()

    def stop_tracking(self) -> Dict:
        """Stop tracking and return summary."""
        if not self._tracking:
            return {}
        snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()
        self._tracking = False

        if len(self._snapshots) < 2:
            return {"error": "Need at least 2 snapshots for diff"}

        stats = snapshot.statistics('lineno')
        top = [(str(s), s.size, s.count) for s in stats[:10]]
        
        # Diff from first snapshot
        diff = snapshot.compare_to(self._snapshots[0], 'lineno')
        top_diff = [(str(d), d.size_diff, d.count_diff) for d in diff[:10]]

        return {
            "current_kb": self._get_current_memory() / 1024,
            "top_allocations": top,
            "top_changes": top_diff,
            "gc_objects": len(gc.get_objects()),
        }

    def _get_current_memory(self) -> int:
        import os
        try:
            import psutil
            return psutil.Process(os.getpid()).memory_info().rss
        except ImportError:
            return 0

    @staticmethod
    def get_object_counts() -> Dict[str, int]:
        """Count objects by type for leak detection."""
        counts = {}
        for obj in gc.get_objects():
            t = type(obj).__name__
            counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1])[:20])


class DatabaseIntegrityChecker:
    """Checks SQLite database integrity at startup."""

    def __init__(self, db_paths: List[str]):
        self.db_paths = db_paths

    def check_all(self) -> List[Tuple[str, bool, str]]:
        """Run integrity check on all databases. Returns (path, ok, message)."""
        import sqlite3
        results = []
        for db_path in self.db_paths:
            p = Path(db_path)
            if not p.exists():
                results.append((db_path, False, "File not found"))
                continue
            try:
                conn = sqlite3.connect(str(p))
                cursor = conn.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                conn.close()
                ok = result == "ok"
                msg = result if not ok else "Integrity OK"
                results.append((db_path, ok, msg))
            except Exception as e:
                results.append((db_path, False, str(e)))
        return results
