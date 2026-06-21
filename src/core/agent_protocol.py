"""
Agent communication protocol for multi-agent delegation.
Addresses NEW-C3#1 (Priya Desai).
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import time


class DelegationMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PIPELINE = "pipeline"
    BROADCAST = "broadcast"


@dataclass
class AgentMessage:
    sender: str
    recipient: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    context_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    message_id: str = ""


@dataclass
class DelegationPlan:
    mode: DelegationMode
    steps: List[Dict[str, Any]] = field(default_factory=list)


class AgentProtocol:
    """Validates and routes messages between agents."""

    VALID_INTENTS = {"delegate", "report", "ask", "respond", "error", "cancel"}

    @staticmethod
    def validate_message(msg: AgentMessage) -> bool:
        if msg.intent not in AgentProtocol.VALID_INTENTS:
            return False
        if not msg.sender or not msg.recipient:
            return False
        return True

    @staticmethod
    def detect_circular_delegation(chain: List[str], new_agent: str) -> bool:
        """Detect if adding an agent would create a circular delegation."""
        if new_agent in chain:
            return True
        return False

    @staticmethod
    def format_plan(plan: DelegationPlan) -> str:
        """Format a delegation plan for display."""
        lines = [f"Delegation Plan ({plan.mode.value}):"]
        for i, step in enumerate(plan.steps):
            agents = step.get("agents", [])
            task = step.get("task", "unknown")
            lines.append(f"  Step {i+1}: {', '.join(agents)} -> {task}")
        return "\n".join(lines)


class DelegationTracker:
    """Track active delegations and detect issues."""

    def __init__(self):
        self._active: Dict[str, List[AgentMessage]] = {}
        self._history: List[AgentMessage] = []

    def start_delegation(self, parent: str, child: str, msg: AgentMessage):
        if parent not in self._active:
            self._active[parent] = []
        self._active[parent].append(msg)
        msg.message_id = f"del_{parent}_{child}_{int(time.time())}"
        self._history.append(msg)

    def complete_delegation(self, msg_id: str):
        for parent, msgs in self._active.items():
            self._active[parent] = [m for m in msgs if m.message_id != msg_id]

    def get_active_count(self, agent: str) -> int:
        return len(self._active.get(agent, []))

    def get_history(self, agent: str) -> List[AgentMessage]:
        return [m for m in self._history if m.sender == agent or m.recipient == agent]

    def get_status(self) -> Dict[str, Any]:
        return {
            "active_delegations": sum(len(v) for v in self._active.values()),
            "total_history": len(self._history),
            "agents": list(self._active.keys()),
        }
