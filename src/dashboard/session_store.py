"""Bounded, idle-expiring browser chat sessions.

Session names are opaque client-generated identifiers, not authentication.
The API key remains the authentication boundary.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable


class SessionCapacityError(RuntimeError):
    """Raised when every retained session is currently active."""


@dataclass
class _Session:
    client: Any
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_access: float = field(default_factory=time.monotonic)
    active: int = 0


class BrowserSessionStore:
    """Serialize each browser session and bound idle session retention."""

    def __init__(self, *, max_sessions: int = 64, idle_ttl: float = 1800.0):
        if max_sessions < 1 or idle_ttl <= 0:
            raise ValueError("max_sessions and idle_ttl must be positive")
        self.max_sessions = max_sessions
        self.idle_ttl = idle_ttl
        self._sessions: dict[str, _Session] = {}
        self._guard = asyncio.Lock()

    @staticmethod
    async def _close(client: Any) -> None:
        close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result

    async def _remove_idle(self, now: float, *, force_one: bool = False) -> list[Any]:
        removed: list[Any] = []
        expired = [
            key for key, entry in self._sessions.items()
            if entry.active == 0 and now - entry.last_access >= self.idle_ttl
        ]
        for key in expired:
            removed.append(self._sessions.pop(key).client)

        if force_one and len(self._sessions) >= self.max_sessions:
            candidates = [
                (entry.last_access, key)
                for key, entry in self._sessions.items()
                if entry.active == 0
            ]
            if candidates:
                _, key = min(candidates)
                removed.append(self._sessions.pop(key).client)
        return removed

    @asynccontextmanager
    async def acquire(
        self,
        session_id: str,
        create_client: Callable[[], Awaitable[Any]],
    ) -> AsyncIterator[Any]:
        """Acquire a serialized session, creating or safely evicting as needed."""
        if not session_id or len(session_id) > 128:
            raise ValueError("session_id must contain 1 to 128 characters")

        async with self._guard:
            now = time.monotonic()
            removed = await self._remove_idle(now)
            entry = self._sessions.get(session_id)
            if entry is None:
                if len(self._sessions) >= self.max_sessions:
                    removed.extend(await self._remove_idle(now, force_one=True))
                if len(self._sessions) >= self.max_sessions:
                    capacity_error = True
                else:
                    capacity_error = False
                    client = await create_client()
                    entry = _Session(client=client)
                    self._sessions[session_id] = entry
            else:
                capacity_error = False
            if not capacity_error:
                entry.active += 1
                entry.last_access = now

        for client in removed:
            await self._close(client)
        if capacity_error:
            raise SessionCapacityError("All browser sessions are active; retry shortly")

        try:
            await entry.lock.acquire()
        except BaseException:
            async with self._guard:
                entry.active -= 1
            raise

        try:
            yield entry.client
        finally:
            entry.lock.release()
            async with self._guard:
                entry.active -= 1
                entry.last_access = time.monotonic()

    async def close_all(self) -> None:
        """Close all idle sessions during application shutdown."""
        async with self._guard:
            active = [key for key, entry in self._sessions.items() if entry.active]
            if active:
                raise RuntimeError("Cannot close browser sessions while requests are active")
            clients = [entry.client for entry in self._sessions.values()]
            self._sessions.clear()
        for client in clients:
            await self._close(client)

    @property
    def retained_count(self) -> int:
        return len(self._sessions)
