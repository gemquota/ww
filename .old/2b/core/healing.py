import asyncio
from typing import Optional
from utils.web_client import WebGeminiClient

class AutoHealer:
    """
    Implements the 'wwfix' loop by escalating failures to Gemini Web for diagnosis.
    """
    def __init__(self, client: Optional[WebGeminiClient] = None):
        self.client = client or WebGeminiClient()

    async def diagnose(self, report: str) -> Optional[str]:
        """
        Sends a failure report to Gemini and returns a fix strategy.
        """
        if not await self.client.init():
            return None

        prompt = (
            f"You are the GEMINI BRIDGE for a local Gemma 2B agent.\n"
            f"The local agent has failed a task. Review the report and provide a DENSED FIX STRATEGY.\n"
            f"Your strategy will be injected back into the 2B agent's loop.\n\n"
            f"{report}\n\n"
            f"Focus on the root cause and a step-by-step correction. Keep it under 200 words."
        )
        
        return await self.client.ask(prompt)
