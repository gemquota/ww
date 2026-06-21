"""
Decision tracing — captures why the agent made specific choices.
Addresses V4-S3: Auditability Gap
"""

from __future__ import annotations

import json
import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from typing import Dict
from pathlib import Path


@dataclass
class DecisionTrace:
    """Records a single agent decision for post-hoc analysis."""
    
    timestamp: str = ""
    task_id: str = ""
    prompt_template_used: str = ""
    template_version: str = ""
    tool_selected: str = ""
    tool_arguments: Dict[str, Any] = field(default_factory=dict)
    memory_entries_consulted: List[str] = field(default_factory=list)
    memory_tiers_used: List[str] = field(default_factory=list)
    reasoning_preview: str = ""
    alternative_tools_considered: List[str] = field(default_factory=list)
    outcome: str = ""


class DecisionTracer:
    """Records decision traces for post-hoc auditability.
    
    Usage:
        tracer = DecisionTracer(log_dir=Path(".tel/traces"))
        trace = tracer.start_trace(task_id="TASK-001")
        trace.tool_selected = "read_file"
        trace.memory_entries_consulted = ["fact: project has 28 modules"]
        tracer.commit(trace)
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self._log_dir = log_dir
        self._traces: List[DecisionTrace] = []
        self._branch_parents: Dict[str, str] = {}
        self._causal = None
    
    def start_trace(self, task_id: str = "") -> DecisionTrace:
        trace = DecisionTrace(
            timestamp=datetime.datetime.now().isoformat(),
            task_id=task_id or f"task-{len(self._traces) + 1}",
        )
        return trace
    
    def commit(self, trace: DecisionTrace) -> None:
        if not trace.timestamp:
            trace.timestamp = datetime.datetime.now().isoformat()
        self._traces.append(trace)
        self._flush(trace)
    
    def _flush(self, trace: DecisionTrace) -> None:
        if not self._log_dir:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / "decision_traces.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(asdict(trace)) + "\n")
    
    def get_traces(self, task_id: Optional[str] = None) -> List[DecisionTrace]:
        if task_id:
            return [t for t in self._traces if t.task_id == task_id]
        return list(self._traces)
    
    def get_reasoning_chain(self, task_id: str) -> List[Dict[str, Any]]:
        """Get the full reasoning chain for a task as a list of steps."""
        traces = self.get_traces(task_id)
        return [
            {
                "step": i,
                "tool": t.tool_selected,
                "reasoning": t.reasoning_preview,
                "outcome": t.outcome,
                "template": f"{t.prompt_template_used}@{t.template_version}",
            }
            for i, t in enumerate(traces)
        ]
    def start_branch(self, parent_task_id: str, branch_name: str = "") -> DecisionTrace:
        """Create a trace that branches from a parent (causal fork)."""
        branch = self.start_trace(task_id=f"{parent_task_id}/{branch_name or 'branch'}")
        branch.reasoning_preview = f"Branched from {parent_task_id}: {branch_name}"
        self._branch_parents[branch.task_id] = parent_task_id
        if self._causal:
            self._causal.create_event(
                event_type="branch",
                parent_ids=[parent_task_id],
                summary=f"Branch: {branch_name or 'unnamed'}",
                data={"child_task": branch.task_id},
            )
        return branch

    def merge_branch(self, branch_task_id: str, into_task_id: str) -> None:
        """Merge a branch back into its parent."""
        parent_id = self._branch_parents.pop(branch_task_id, None)
        if parent_id and self._causal:
            self._causal.create_event(
                event_type="merge",
                parent_ids=[branch_task_id, into_task_id],
                summary=f"Merged {branch_task_id} -> {into_task_id}",
            )

    def set_causal_graph(self, graph) -> None:
        """Attach a CausalGraph for persistent event recording."""
        self._causal = graph

    @property
    def branches(self) -> Dict[str, str]:
        """Active branches: branch_task_id -> parent_task_id."""
        return dict(self._branch_parents)
