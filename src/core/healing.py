"""
Auto-healing system: escalates failures to Gemini Web API for diagnosis.

Implements the escalation pattern from 2b/harness:
local retry (x3) → Gemini Web diagnosis → fix strategy injection

Supports optional PCG (Procedural Causal Graph) data from the memory
system to provide causal chain context in failure reports.
"""
from typing import Optional, List, Dict, Any
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
