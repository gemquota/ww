"""Benchmark evaluation judge using Gemini Web API."""
import json
import re
from typing import Dict, Any, Optional
from src.utils.web_client import WebGeminiClient


class BenchmarkJudge:
    """Evaluates execution traces against success criteria via Gemini Web."""

    def __init__(self, client: Optional[WebGeminiClient] = None):
        self.client = client

    async def evaluate(self, trace_json: str, prompt: str, success_criteria: str) -> Dict[str, Any]:
        if self.client is None:
            return {"error": "No Gemini client available", "score": 0.0}
        if not await self.client.init():
            return {"success": False, "reason": "No judge client available."}

        evaluation_prompt = f"""
Evaluate the following agent execution trace against the success criteria.

### TASK
{prompt}

### SUCCESS CRITERIA
{success_criteria}

### EXECUTION TRACE
{trace_json}

### INSTRUCTIONS
1. Analyze the agent's reasoning (thoughts).
2. Check if the tool calls were appropriate and their outputs handled correctly.
3. Determine if the final answer or final state satisfies the success criteria.
4. Provide a JSON response with:
   - "success": boolean
   - "reason": string explanation
"""
        try:
            response_text = await self.client.ask(evaluation_prompt)
            if not response_text:
                return {"success": False, "reason": "Empty response from judge."}
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"success": False, "reason": "Could not parse judge response."}
        except Exception as e:
            return {"success": False, "reason": f"Judge error: {str(e)}"}
