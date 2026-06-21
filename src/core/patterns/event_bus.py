"""
Simple event bus for decoupled communication between components.
Addresses V4-M3: Feature Coupling
"""

from __future__ import annotations

import enum
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(enum.Enum):
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    TOOL_EXECUTED = "tool_executed"
    TOOL_FAILED = "tool_failed"
    MEMORY_FLUSHED = "memory_flushed"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"
    PROMPT_RENDERED = "prompt_rendered"
    AGENT_DELEGATED = "agent_delegated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


EventHandler = Callable[[EventType, Dict[str, Any]], None]


class EventBus:
    """Simple synchronous event bus for component decoupling."""

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister a handler."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]

    def emit(self, event_type: EventType, data: Optional[Dict[str, Any]] = None) -> None:
        """Emit an event to all registered handlers."""
        logger.debug(f"Event: {event_type.value} {data or {}}")
        for handler in self._handlers.get(event_type, []):
            try:
                handler(event_type, data or {})
            except Exception:
                logger.exception(f"Handler failed for event {event_type.value}")

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()


# Global singleton for convenience
_bus: Optional[EventBus] = None
_warned = False


def get_bus() -> EventBus:
    global _bus, _warned
    if not _warned:
        import warnings
        warnings.warn(
            "get_bus() is deprecated. Pass EventBus instance via BridgeContext instead.",
            DeprecationWarning, stacklevel=2
        )
        _warned = True
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def reset_bus() -> None:
    global _bus
    import warnings
    warnings.warn(
        "reset_bus() is deprecated. EventBus lifecycle should be managed via BridgeContext.",
        DeprecationWarning, stacklevel=2
    )
    _bus = None
