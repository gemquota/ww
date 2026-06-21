"""V7 integration engine — wires all V7 modules into the WW Bridge runtime.
Enables enforcement hooks, scheduled checks, and report generation for all 19 characters.
"""
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class V7IntegrationEngine:
    """Central engine that runs all V7 checks and integrates with the runtime."""

    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path.cwd()
        self._results: Dict[str, Any] = {}
        self._last_run: Optional[float] = None

    def run_architecture_checks(self) -> Dict:
        """Run V7-01/04 architecture checks."""
        from src.v7.architecture import ModularityChecker, DependencyGraph
        checker = ModularityChecker(self.root)
        graph = DependencyGraph(self.root)
        cycles = graph.find_cycles()
        return {
            "layer_violations": len(checker.check_layer_violations()),
            "abstraction_violations": len(checker.check_abstraction_boundaries()),
            "dependency_cycles": len(cycles),
            "score": checker.report()["score"],
        }

    def run_distributed_systems_checks(self) -> Dict:
        """Run V7-02 distributed systems checks."""
        from src.v7.distributed_systems import PartitionHandler, EventDrivenArchitecture
        ph = PartitionHandler()
        eda = EventDrivenArchitecture()
        return {
            "active_partitions": len(ph.get_active()),
            "orphan_events": eda.find_orphan_events(),
        }

    def run_quality_checks(self) -> Dict:
        """Run V7-03/06 quality/maintainability checks."""
        from src.v7.quality import TechDebtTracker
        from src.v7.maintainability import GodObjectDetector, CouplingAnalyzer
        tracker = TechDebtTracker()
        detector = GodObjectDetector()
        ca = CouplingAnalyzer(self.root)
        gods = detector.scan_all(self.root)
        coupling = ca.measure_coupling()
        return {
            "tech_debt_unresolved": len(tracker.get_unresolved()),
            "god_objects": len(gods),
            "highly_coupled_pairs": coupling.get("highly_coupled_pairs", 0),
        }

    def run_reliability_checks(self) -> Dict:
        """Run V7-07 reliability checks."""
        from src.v7.reliability import ChaosReadiness
        chaos = ChaosReadiness.check_readiness(self.root)
        return {"chaos_readiness": chaos}

    def run_security_checks(self) -> Dict:
        """Run V7-12 security checks."""
        from src.v7.security import SecurityAuditor, TrustBoundaryValidator
        auditor = SecurityAuditor()
        return {
            "file_permission_issues": len(auditor.check_file_permissions(self.root)),
            "template_injection_points": len(TrustBoundaryValidator.check_template_injection_points(self.root)),
        }

    def run_ecosystem_checks(self) -> Dict:
        """Run V7-17 ecosystem checks."""
        from src.v7.ecosystem import CommunityHealth
        ch = CommunityHealth()
        return {"community_files": ch.check_files(self.root)}

    def run_all(self) -> Dict:
        """Run all V7 checks and return comprehensive report."""
        self._results = {
            "timestamp": datetime.now().isoformat(),
            "architecture": self.run_architecture_checks(),
            "distributed_systems": self.run_distributed_systems_checks(),
            "quality": self.run_quality_checks(),
            "reliability": self.run_reliability_checks(),
            "security": self.run_security_checks(),
            "ecosystem": self.run_ecosystem_checks(),
        }
        self._last_run = time.time()
        return self._results

    def get_score(self) -> int:
        """Get overall health score (0-100)."""
        if not self._results:
            self.run_all()
        deductions = 0
        arch = self._results.get("architecture", {})
        deductions += arch.get("layer_violations", 0) * 5
        deductions += arch.get("dependency_cycles", 0) * 10
        deductions += arch.get("abstraction_violations", 0) * 3
        qual = self._results.get("quality", {})
        deductions += qual.get("god_objects", 0) * 8
        deductions += qual.get("tech_debt_unresolved", 0) * 2
        return max(0, 100 - deductions)

    def summary(self) -> str:
        """Generate a one-line summary of V7 health."""
        score = self.get_score()
        issues = []
        arch = self._results.get("architecture", {})
        if arch.get("layer_violations", 0) > 0:
            issues.append(f"{arch['layer_violations']} layer violations")
        if arch.get("dependency_cycles", 0) > 0:
            issues.append(f"{arch['dependency_cycles']} dependency cycles")
        qual = self._results.get("quality", {})
        if qual.get("god_objects", 0) > 0:
            issues.append(f"{qual['god_objects']} god objects")
        status = "healthy" if score >= 80 else "needs attention"
        return f"V7 Score: {score}/100 ({status})" + (f" — {', '.join(issues)}" if issues else "")
