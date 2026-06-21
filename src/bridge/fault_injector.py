"""
Fault injection framework for testing failure recovery.
Addresses V4-R3: Missing Failure Injection Framework
"""

from __future__ import annotations

import contextlib
import threading
from typing import Dict, Optional, Set, Type


class _FaultConfig:
    def __init__(self):
        self._fail_on: Dict[str, Exception] = {}
        self._lock = threading.Lock()

    def inject(self, target: str, error: Exception) -> None:
        with self._lock:
            self._fail_on[target] = error

    def clear(self, target: Optional[str] = None) -> None:
        with self._lock:
            if target:
                self._fail_on.pop(target, None)
            else:
                self._fail_on.clear()

    def should_fail(self, target: str) -> Optional[Exception]:
        with self._lock:
            return self._fail_on.get(target)

    def is_active(self) -> bool:
        with self._lock:
            return len(self._fail_on) > 0


_fault_config = _FaultConfig()


def should_fail(target: str) -> None:
    """Check if a fault is configured for the given target.
    Raises the configured exception if so. Call at specific failure points.
    """
    error = _fault_config.should_fail(target)
    if error is not None:
        raise error


@contextlib.contextmanager
def FaultInjector(target: str, error: Exception):
    """Context manager that injects a fault at a specific target point.
    
    Example:
        with FaultInjector("sqlite_commit", IOError("disk full")):
            memory.flush()  # Will raise IOError if flush calls should_fail("sqlite_commit")
    """
    _fault_config.inject(target, error)
    try:
        yield
    finally:
        _fault_config.clear(target)


def reset_faults() -> None:
    _fault_config.clear()
