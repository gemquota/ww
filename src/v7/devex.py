"""V7-05: Developer experience improvements (Jamie Vega)."""
import time
from pathlib import Path
from typing import Dict, List, Optional


class OnboardingMetrics:
    """Track onboarding effectiveness metrics."""

    def __init__(self):
        self._start_times: Dict[str, float] = {}

    def start_onboarding(self, user_id: str):
        self._start_times[user_id] = time.time()

    def complete_onboarding(self, user_id: str) -> Optional[float]:
        start = self._start_times.pop(user_id, None)
        if start:
            return time.time() - start
        return None

    def get_time_to_first_query(self, user_id: str) -> Optional[float]:
        """Time from session start to first user query."""
        return self._start_times.get(user_id)


class CodeQualityTooling:
    """Aggregate code quality checks for DevEx."""

    @staticmethod
    def check_all(paths: List[Path]) -> Dict[str, int]:
        """Run all quality checks and return counts."""
        result = {"syntax_errors": 0, "import_errors": 0, "ok": 0}
        for path in paths:
            if path.suffix == ".py":
                try:
                    compile(path.read_text(), str(path), "exec")
                    result["ok"] += 1
                except SyntaxError:
                    result["syntax_errors"] += 1
                except Exception:
                    result["import_errors"] += 1
        return result


class TestCoverageCulture:
    """Track and encourage test coverage culture."""

    def __init__(self, src_root: Path = Path("src"),
                 test_root: Path = Path(".tel/tests")):
        self.src_root = src_root
        self.test_root = test_root

    def get_coverage_ratio(self) -> float:
        """Get ratio of test files to source modules."""
        src_files = list(self.src_root.rglob("*.py"))
        test_files = list(self.test_root.rglob("test_*.py"))
        if not src_files:
            return 0.0
        return round(len(test_files) / max(len(src_files), 1), 2)

    def get_uncovered_modules(self) -> List[str]:
        """Find source modules without corresponding test files."""
        uncovered = []
        for pyfile in sorted(self.src_root.rglob("**/*.py")):
            if pyfile.name == "__init__.py":
                continue
            rel = str(pyfile.relative_to(self.src_root))
            test_name = f"test_{pyfile.stem}.py"
            test_path = self.test_root / test_name
            if not test_path.exists():
                uncovered.append(rel)
        return uncovered
