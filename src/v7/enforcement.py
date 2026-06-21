"""V7 enforcement hooks — active guards that prevent architecture degradation.
Wires into CI pipeline and runtime for continuous enforcement.
"""
from pathlib import Path
from typing import List, Dict, Optional, Callable


class EnforcementRule:
    """A single architecture enforcement rule."""

    def __init__(self, name: str, check_fn: Callable, severity: str = "error",
                 message: str = ""):
        self.name = name
        self.check_fn = check_fn
        self.severity = severity
        self.message = message

    def check(self) -> bool:
        """Run the check. Returns True if passing."""
        try:
            return self.check_fn()
        except Exception:
            return False


class EnforcementEngine:
    """Runs all enforcement rules and reports failures."""

    def __init__(self):
        self._rules: List[EnforcementRule] = []

    def register(self, rule: EnforcementRule):
        self._rules.append(rule)

    def register_all(self):
        """Register all V7 enforcement rules."""

        # V7-01: No circular dependencies
        def check_no_cycles():
            from src.v7.architecture import DependencyGraph
            return len(DependencyGraph(Path.cwd()).find_cycles()) == 0
        self.register(EnforcementRule("no-circular-deps", check_no_cycles, "error",
                                      "Circular dependencies detected"))

        # V7-01: No layer violations
        def check_layer_violations():
            from src.v7.architecture import ModularityChecker
            return len(ModularityChecker(Path.cwd()).check_layer_violations()) == 0
        self.register(EnforcementRule("no-layer-violations", check_layer_violations, "error",
                                      "Cross-layer import violations detected"))

        # V7-03: Tech debt threshold
        def check_tech_debt():
            from src.v7.quality import TechDebtTracker
            return len(TechDebtTracker().get_unresolved()) < 20
        self.register(EnforcementRule("tech-debt-threshold", check_tech_debt, "warning",
                                      "Too many unresolved tech debt items"))

        # V7-06: No god objects
        def check_god_objects():
            from src.v7.maintainability import GodObjectDetector
            return len(GodObjectDetector().scan_all(Path.cwd())) == 0
        self.register(EnforcementRule("no-god-objects", check_god_objects, "warning",
                                      "God objects detected"))

        # V7-12: Security posture
        def check_security():
            from src.v7.security import SecurityAuditor
            return len(SecurityAuditor().check_hardcoded_secrets(Path.cwd())) == 0
        self.register(EnforcementRule("no-hardcoded-secrets", check_security, "error",
                                      "Potential hardcoded secrets found"))

        # V7-13: Documentation coverage
        def check_docstring_coverage():
            from src.v7.documentation import APIDocQuality
            result = APIDocQuality.check_docstring_coverage(Path.cwd())
            return result.get("coverage_pct", 0) >= 30
        self.register(EnforcementRule("docstring-coverage", check_docstring_coverage, "warning",
                                      "Docstring coverage below 30%"))

    def run_all(self) -> Dict:
        """Run all registered rules. Returns pass/fail per rule."""
        self.register_all()
        results = {}
        for rule in self._rules:
            passed = rule.check()
            results[rule.name] = {
                "passed": passed,
                "severity": rule.severity,
                "message": rule.message if not passed else "",
            }
        return results

    def can_merge(self) -> bool:
        """Check if all error-severity rules pass (for CI gating)."""
        results = self.run_all()
        return all(
            r["passed"]
            for r in results.values()
            if r["severity"] == "error"
        )

    def summary(self) -> str:
        results = self.run_all()
        total = len(results)
        passed = sum(1 for r in results.values() if r["passed"])
        errors = sum(1 for r in results.values()
                     if not r["passed"] and r["severity"] == "error")
        warnings = sum(1 for r in results.values()
                       if not r["passed"] and r["severity"] == "warning")
        return (f"Enforcement: {passed}/{total} passing "
                f"({errors} errors, {warnings} warnings)")
