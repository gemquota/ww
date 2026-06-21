"""
Benchmark harness for structured task evaluation with execution traces.

Self-contained: accepts a callable execute_fn(task_prompt, trace)
instead of depending on an external harness object.
"""
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
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
    status: str = "PENDING"


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


class BenchmarkHarness:
    """Runs benchmark tasks against a callable and collects traces.

    Args:
        execute_fn: Async callable fn(prompt, trace) -> bool. Called for each task.
        judge: Optional judge for evaluation.
    """

    def __init__(self, execute_fn: Optional[Callable] = None, judge=None, timeout_seconds: Optional[int] = None):
        self.execute_fn = execute_fn or self._default_execute
        self.judge = judge
        self.timeout_seconds = timeout_seconds
        self.results_dir = Path(".tests/results/runs")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def _default_execute(self, prompt: str, trace: ExecutionTrace) -> bool:
        """Default stub that marks task as not executed."""
        trace.status = "NOT_IMPLEMENTED"
        trace.final_answer = "No harness execute_fn provided."
        return False

    async def run_task(self, task: Dict[str, Any], attempt: int = 1) -> BenchmarkResult:
        task_id = task.get("id", "unknown")
        task_name = task.get("name", "Unnamed Task")
        prompt = task.get("query") or task.get("prompt") or ""
        success_criteria = task.get("success_criteria") or str(task.get("expected_substrings", ""))

        trace = ExecutionTrace(
            task_id=task_id, task_name=task_name,
            prompt=prompt, success_criteria=success_criteria
        )

        start_time = time.time()
        timeout = self.timeout_seconds if hasattr(self, 'timeout_seconds') and self.timeout_seconds else (300 if attempt <= 2 else 600)

        try:
            task_success = await asyncio.wait_for(
                self.execute_fn(prompt, trace),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            task_success = False
            trace.status = "TIMEOUT"
            trace.final_answer = f"Task timed out after {timeout}s"
        except Exception as e:
            task_success = False
            trace.status = "ERROR"
            trace.final_answer = f"Error: {str(e)}"

        trace.duration = time.time() - start_time
        trace.total_steps = len(trace.steps)
        success = task_success
        if trace.status == "PENDING":
            trace.status = "SUCCESS" if success else "FAILURE"

        trace_file = self.results_dir / f"{task_id}_{int(time.time())}.json"
        with open(trace_file, "w") as f:
            f.write(trace.model_dump_json(indent=2))

        # Simple evaluation: substring match
        precision, recall, info_loss = None, None, None
        expected = task.get("expected_substrings", [])
        actual = (trace.final_answer or "").lower()
        if expected:
            found = sum(1 for sub in expected if sub.lower() in actual)
            recall = found / len(expected)
            info_loss = 1.0 - recall
            precision = 1.0 if found == len(expected) else (found / len(expected) if len(expected) > 0 else 0)

        verdict = {"success": success, "reason": trace.status}
        if recall is not None:
            verdict["reason"] = f"Recall: {recall:.2f}" if recall < 1.0 else "All substrings found."
            verdict["success"] = recall == 1.0

        return BenchmarkResult(
            task_id=task_id, success=verdict["success"], reason=verdict["reason"],
            steps=trace.total_steps, duration=trace.duration,
            trace_path=str(trace_file), precision=precision,
            recall=recall, info_loss=info_loss
        )

    async def run_suite(self, suite_path: str) -> List[BenchmarkResult]:
        with open(suite_path, "r") as f:
            suite = json.load(f)

        results = []
        for task in suite:
            print(f"  Running: {task.get('name', task.get('id'))}")
            last_result = None
            for attempt in range(1, 4):
                if attempt > 1:
                    print(f"    Attempt {attempt}...")
                result = await self.run_task(task, attempt=attempt)
                last_result = result
                if result.success:
                    break
            results.append(last_result)
            status = "PASSED" if last_result.success else "FAILED"
            print(f"    {status} - {last_result.reason[:80]}")
        return results
