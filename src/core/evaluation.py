"""
Evaluation framework for AI quality assessment.
Addresses NEW-C1#1 (Dr. Rajesh Patel).
Per-type metrics — NEW-V5-C1#4.
"""
import json
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class EvalResult:
    test_id: str
    category: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvaluationSuite:
    """Run and track evaluation results for AI quality metrics."""

    def __init__(self, suite_name: str, results_dir: Optional[Path] = None):
        self.suite_name = suite_name
        self.results_dir = results_dir or Path(".eval")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[EvalResult] = []
        # Per-type metrics aggregator (C1#4)
        from src.core.decomposition import MetricsAggregator
        self._metrics = MetricsAggregator()
        self._categories: set = set()

    def run_test(
        self,
        test_id: str,
        category: str,
        test_fn,
        *args,
        **kwargs,
    ) -> EvalResult:
        """Run a single evaluation test and record per-type metrics."""
        start = time.time()
        try:
            passed, score, details = test_fn(*args, **kwargs)
            duration_ms = (time.time() - start) * 1000
            result = EvalResult(
                test_id=test_id,
                category=category,
                passed=passed,
                score=score,
                details=details,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            result = EvalResult(
                test_id=test_id,
                category=category,
                passed=False,
                score=0.0,
                details=f"Test raised exception: {e}",
                duration_ms=duration_ms,
            )
        self.results.append(result)
        self._categories.add(category)
        # Auto-record per-type metric (C1#4)
        self._metrics.record(category, result.score)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the suite."""
        if not self.results:
            return {"suite": self.suite_name, "total": 0, "passed": 0, "score": 0.0}
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        avg_score = sum(r.score for r in self.results) / total
        return {
            "suite": self.suite_name,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "average_score": round(avg_score, 3),
            "pass_rate": round(passed / total * 100, 1),
            "categories": sorted(self._categories),
        }

    def get_per_type_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get per-type metrics breakdown (C1#4)."""
        return self._metrics.get_summary()

    def save_report(self, filename: Optional[str] = None) -> Path:
        """Save results to a JSON file with per-type metrics."""
        if not filename:
            filename = f"eval_{self.suite_name}_{int(time.time())}.json"
        path = self.results_dir / filename
        data = {
            "suite": self.suite_name,
            "timestamp": time.time(),
            "summary": self.get_summary(),
            "per_type_metrics": self.get_per_type_metrics(),
            "results": [asdict(r) for r in self.results],
        }
        path.write_text(json.dumps(data, indent=2))
        return path

    def get_formatted_report(self) -> str:
        """Generate human-readable report with per-type breakdown."""
        lines = [f"=== {self.suite_name} Evaluation Report ==="]
        summary = self.get_summary()
        lines.append(f"Total: {summary['total']} | Passed: {summary['passed']} "
                     f"| Failed: {summary['failed']} | Rate: {summary['pass_rate']}%")
        per_type = self.get_per_type_metrics()
        if per_type:
            lines.append("\n--- Per-Type Metrics ---")
            for cat, stats in sorted(per_type.items()):
                lines.append(f"  {cat}: count={stats['count']}, mean={stats['mean']}, "
                             f"min={stats['min']}, max={stats['max']}")
        return "\n".join(lines)


# Quality analyzers
def analyze_prompt_quality(prompt: str) -> Dict[str, Any]:
    """Analyze a prompt for quality metrics."""
    return {
        "length": len(prompt),
        "has_examples": "example" in prompt.lower(),
        "has_constraints": any(w in prompt.lower() for w in ["must", "should", "avoid", "don"]),
        "has_context": len(prompt) > 100,
        "specificity_score": min(1.0, len(prompt) / 500),
    }


def check_tool_safety(tool_name: str, args: dict) -> Dict[str, Any]:
    """Check tool invocation for safety concerns."""
    warnings = []
    if tool_name == "shell_exec" and "rm" in args.get("command", ""):
        warnings.append("Destructive shell command detected")
    if tool_name == "write_file" and "/etc/" in args.get("path", ""):
        warnings.append("System file write detected")
    return {"safe": len(warnings) == 0, "warnings": warnings}
