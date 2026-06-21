import json
import time
import os
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TraceStep(BaseModel):
    step_number: int
    thought: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    error: Optional[str] = None

class ExecutionTrace(BaseModel):
    task_id: str
    task_name: str
    prompt: str
    success_criteria: str
    steps: List[TraceStep] = []
    final_answer: Optional[str] = None
    total_steps: int = 0
    duration: float = 0.0
    status: str = "PENDING" # PENDING, SUCCESS, FAILURE, ERROR

class BenchmarkResult(BaseModel):
    task_id: str
    success: bool
    reason: str
    steps: int
    duration: float
    trace_path: str
    precision: Optional[float] = None
    recall: Optional[float] = None
    info_loss: Optional[float] = None

from core.judge import BenchmarkJudge

class BenchmarkHarness:
    def __init__(self, agent_harness, judge=None):
        self.harness = agent_harness
        self.judge = judge
        self.results_dir = Path("benchmarks/runs")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def run_task(self, task: Dict[str, Any], attempt: int = 1) -> BenchmarkResult:
        task_id = task.get("id", "unknown")
        task_name = task.get("name", "Unnamed Task")
        
        # Handle multi-turn tasks or facts
        turns = task.get("turns", [])
        facts = task.get("facts", [])
        
        # Pre-populate memory
        self.harness.agent.clear_history()
        self.harness.memory.clear_history()
        for fact in facts:
            self.harness.memory.add_turn("system", fact)
        
        prompt = ""
        if turns:
            # Add all but the last turn to memory
            for turn in turns[:-1]:
                self.harness.memory.add_turn(turn["role"], turn["content"])
            prompt = turns[-1]["content"]
        else:
            prompt = task.get("query") or task.get("prompt") or ""
            
        # success_criteria might be substrings for now, but we want the judge to use it
        success_criteria = task.get("success_criteria") or str(task.get("expected_substrings", ""))
        
        trace = ExecutionTrace(
            task_id=task_id,
            task_name=task_name,
            prompt=prompt,
            success_criteria=success_criteria
        )
        
        start_time = time.time()
        
        # Implement Timeout: 30s initial, 60s if attempt > 3
        timeout = 30 if attempt <= 3 else 60
        
        try:
            success = await asyncio.wait_for(
                self.harness.execute_task_with_trace(prompt, trace),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            success = False
            trace.status = "TIMEOUT"
            trace.final_answer = f"Task timed out after {timeout}s"
        except Exception as e:
            success = False
            trace.status = "ERROR"
            trace.final_answer = f"Error during execution: {str(e)}"
        
        trace.duration = time.time() - start_time
        trace.total_steps = len(trace.steps)
        if trace.status == "PENDING":
            trace.status = "SUCCESS" if success else "FAILURE"
        
        trace_file = self.results_dir / f"{task_id}_{int(time.time())}.json"
        with open(trace_file, "w") as f:
            f.write(trace.model_dump_json(indent=2))
            
        # Telemetry Log
        from core.telemetry import telemetry
        telemetry.log(self.harness.session_id, "benchmark_task", {
            "task_id": task_id,
            "success": success,
            "duration": trace.duration,
            "steps": trace.total_steps,
            "status": trace.status,
            "attempt": attempt
        })

        # Evaluation by Judge
        precision, recall, info_loss = None, None, None
        expected = task.get("expected_substrings", [])
        actual = (trace.final_answer or "").lower()

        if expected:
            found = sum(1 for sub in expected if sub.lower() in actual)
            recall = found / len(expected)
            info_loss = 1.0 - recall
            precision = 1.0 if found == len(expected) else (found / len(expected) if len(expected) > 0 else 0)

        if self.judge:
            verdict = await self.judge.evaluate(
                trace.model_dump_json(indent=2),
                trace.prompt,
                trace.success_criteria
            )
            # If judge provides detailed metrics, use them
            if "precision" in verdict: precision = verdict["precision"]
            if "recall" in verdict: recall = verdict["recall"]
            if "info_loss" in verdict: info_loss = verdict["info_loss"]
        else:
            # Fallback to simple substring check if no judge
            passed = recall == 1.0 if recall is not None else success
            reason = "Simple substring check."
            if not passed:
                reason = f"Missing expected substrings. Recall: {recall:.2f}" if recall is not None else "Execution failed."
            verdict = {"success": passed, "reason": reason}
            
        return BenchmarkResult(
            task_id=task_id,
            success=verdict["success"],
            reason=verdict["reason"],
            steps=trace.total_steps,
            duration=trace.duration,
            trace_path=str(trace_file),
            precision=precision,
            recall=recall,
            info_loss=info_loss
        )

    async def run_suite(self, suite_path: str) -> List[BenchmarkResult]:
        with open(suite_path, "r") as f:
            suite = json.load(f)
            
        results = []
        for task in suite:
            print(f"Running Task: {task.get('name', task.get('id'))}")
            
            # Retry logic: up to 6 attempts (3 at 30s, 3 at 60s)
            last_result = None
            for attempt in range(1, 7):
                if attempt > 1:
                    print(f"  Attempt {attempt}...")
                
                result = await self.run_task(task, attempt=attempt)
                last_result = result
                if result.success:
                    break
            
            results.append(last_result)
            status = "PASSED" if last_result.success else "FAILED"
            print(f"Result: {status} - {last_result.reason}")
            
        return results
