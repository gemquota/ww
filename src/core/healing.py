"""
Auto-healing system: escalates failures to Gemini Web API for diagnosis.

Implements the escalation pattern from 2b/harness:
local retry (x3) → Gemini Web diagnosis → fix strategy injection

Supports optional PCG (Procedural Causal Graph) data from the memory
system to provide causal chain context in failure reports.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from src.core.utils.web_client import WebGeminiClient


class AutoHealer:
    """
    Escalates failure reports to Gemini Web for diagnosis and fix strategy.

    Used after N local failures to get a higher-quality recovery plan.
    Optionally accepts PCG causal chains from MemoryManager for richer context.
    """

    def __init__(self, client: Optional[WebGeminiClient] = None):
        self.client = client

    async def diagnose(
        self,
        report: str,
        pcg_chains: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """
        Sends a failure report (optionally with PCG causal chains) to Gemini
        and returns a fix strategy.

        Args:
            report: Detailed failure report including the task, what was
                   attempted, what went wrong, and any error messages.
            pcg_chains: Optional list of causal chain dicts from MemoryGraph
                       (keys: source, type, target).

        Returns:
            A fix strategy string, or None if diagnosis failed.
        """
        if self.client is None:
            return None
        if not await self.client.init():
            return None

        # Build enhanced report with PCG context if available
        enhanced_report = report
        if pcg_chains:
            chain_text = "\n".join(
                f"  {c.get('source', '?')} --[{c.get('type', '?')}]--> {c.get('target', '?')}"
                for c in pcg_chains
            )
            enhanced_report += (
                "\n\nCAUSAL CHAINS (from PCG memory graph):\n"
                f"{chain_text}\n"
            )

        prompt = (
            "You are the DIAGNOSTIC BRIDGE for a Gemini-powered agent harness.\n"
            "The agent has failed a task. Review the report and causal chains "
            "below and provide a DENSE FIX STRATEGY.\n"
            "Your strategy will be injected back into the agent's execution loop.\n\n"
            f"{enhanced_report}\n\n"
            "Focus on the root cause and a step-by-step correction. "
            "Keep it under 200 words. Be specific about what tool calls to make."
        )

        return await self.client.ask(prompt)


# ── Merged from incident_response.py (# Incident response) ──
class Incident:
    """Represents a single incident with severity classification."""

    SEVERITIES = ["critical", "major", "minor", "warning"]

    def __init__(self, title: str, severity: str = "minor"):
        assert severity in self.SEVERITIES, f"Invalid severity: {severity}"
        self.id = f"inc_{int(time.time())}"
        self.title = title
        self.severity = severity
        self.timestamp = datetime.now().isoformat()
        self.resolved_at: Optional[str] = None
        self.actions: List[str] = []
        self.notes: str = ""

    def resolve(self):
        self.resolved_at = datetime.now().isoformat()

    def add_action(self, action: str):
        self.actions.append(action)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "resolved_at": self.resolved_at,
            "actions": self.actions,
            "notes": self.notes,
        }


class PostMortem:
    """Post-incident review and analysis."""

    def __init__(self, incident: Incident):
        self.incident = incident
        self.what_happened: str = ""
        self.root_cause: str = ""
        self.timeline: List[Dict] = []
        self.action_items: List[str] = []
        self.preventive_measures: List[str] = []

    def add_timeline_entry(self, time_str: str, event: str):
        self.timeline.append({"time": time_str, "event": event})

    def to_report(self) -> str:
        lines = [
            "=" * 60,
            f"POST-MORTEM: {self.incident.title}",
            f"Severity: {self.incident.severity.upper()}",
            f"Date: {self.incident.timestamp}",
            "=" * 60,
            "",
            "## What Happened",
            self.what_happened or "(pending)",
            "",
            "## Root Cause",
            self.root_cause or "(pending)",
            "",
            "## Timeline",
        ]
        for entry in self.timeline:
            lines.append(f"  {entry['time']} — {entry['event']}")
        lines.extend([
            "",
            "## Action Items",
        ])
        for item in self.action_items:
            lines.append(f"  [ ] {item}")
        lines.extend([
            "",
            "## Preventive Measures",
        ])
        for item in self.preventive_measures:
            lines.append(f"  [ ] {item}")
        return "\n".join(lines)


class ChaosExperiment:
    """Chaos engineering experiment definition."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.hypothesis: str = ""
        self.procedure: List[str] = []
        self.expected_outcome: str = ""
        self.actual_outcome: str = ""
        self.passed: Optional[bool] = None

    def run(self) -> Dict:
        """Execute the experiment. Returns results dict."""
        result = {
            "experiment": self.name,
            "hypothesis": self.hypothesis,
            "passed": self.passed,
            "actual_outcome": self.actual_outcome,
        }
        return result


class IncidentResponse:
    """Coordinates incident response activities."""

    def __init__(self, log_dir: str = ".tel/incidents"):
        self.log_dir = Path.cwd() / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.active_incidents: Dict[str, Incident] = {}

    def declare(self, title: str, severity: str = "minor") -> Incident:
        inc = Incident(title, severity)
        self.active_incidents[inc.id] = inc
        self._save_incident(inc)
        return inc

    def resolve(self, inc_id: str):
        if inc_id in self.active_incidents:
            self.active_incidents[inc_id].resolve()
            self._save_incident(self.active_incidents[inc_id])

    def _save_incident(self, inc: Incident):
        path = self.log_dir / f"{inc.id}.json"
        path.write_text(json.dumps(inc.to_dict(), indent=2))
