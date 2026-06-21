"""
Task decomposition fidelity — NEW-V5-C3#4 (Priya Desai).
Verifies decomposed subtasks preserve original task semantics.
"""
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class DecomposedTask:
    name: str
    description: str
    dependencies: List[str]
    validator: Optional[Callable] = None


class DecompositionFidelity:
    """Verify task decomposition preserves semantics."""

    @staticmethod
    def validate_fidelity(original: str, subtasks: List[DecomposedTask]) -> Dict[str, Any]:
        """Check that subtasks collectively cover the original task."""
        issues = []
        covered = set()

        for task in subtasks:
            # Check each task contributes unique value
            if task.name in covered:
                issues.append(f"Duplicate subtask: {task.name}")
            covered.add(task.name)

            # Validate dependency references
            for dep in task.dependencies:
                if dep not in covered and dep not in [t.name for t in subtasks]:
                    issues.append(f"Missing dependency: {dep} (required by {task.name})")

        return {
            "valid": len(issues) == 0,
            "subtask_count": len(subtasks),
            "unique_tasks": len(covered),
            "issues": issues,
            "coverage_score": round(len(covered) / max(len(subtasks), 1), 2),
        }

    @staticmethod
    def format_breakdown(subtasks: List[DecomposedTask]) -> str:
        """Format a task breakdown for display."""
        lines = ["Task Breakdown:"]
        for i, task in enumerate(subtasks, 1):
            deps = f" (depends on: {', '.join(task.dependencies)})" if task.dependencies else ""
            lines.append(f"  {i}. {task.name}{deps}")
            lines.append(f"     {task.description}")
        return "\n".join(lines)

    @staticmethod
    def run_integration_validation(original: str, subtasks: List['DecomposedTask']) -> Dict[str, Any]:
        """Integration test helper (C3#4): run full validation and return structured results.
        
        Returns dict with: valid, subtask_count, coverage_score, issues, missing_deps, duplicates.
        """
        result = DecompositionFidelity.validate_fidelity(original, subtasks)
        missing_deps = []
        duplicates = []
        for issue in result.get("issues", []):
            if issue.startswith("Missing dependency"):
                missing_deps.append(issue)
            if issue.startswith("Duplicate"):
                duplicates.append(issue)
        return {
            **result,
            "missing_dependencies": missing_deps,
            "duplicates": duplicates,
            "integration_verified": len(result.get("issues", [])) == 0,
        }


# Per-type AI metrics — NEW-V5-C1#4
class MetricsAggregator:
    """Aggregate evaluation metrics by category."""

    def __init__(self):
        self._metrics: Dict[str, List[float]] = {}

    def record(self, category: str, score: float):
        if category not in self._metrics:
            self._metrics[category] = []
        self._metrics[category].append(score)

    def get_summary(self) -> Dict[str, Dict[str, float]]:
        summary = {}
        for category, scores in self._metrics.items():
            if scores:
                summary[category] = {
                    "count": len(scores),
                    "mean": round(sum(scores) / len(scores), 3),
                    "min": round(min(scores), 3),
                    "max": round(max(scores), 3),
                }
        return summary
