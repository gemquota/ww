"""Minimal stateful transport for Gemini Web Chat.

No agent framework, tool execution, API-key backend, workspace access, or
orchestration belongs in this module. One WWClient owns one remote chat.
"""
from __future__ import annotations

import inspect
import os
from collections.abc import AsyncIterator, Callable
from typing import Any


class WWClient:
    """Authenticate to Gemini Web Chat and exchange conversational messages."""

    def __init__(
        self,
        secure_1psid: str = "",
        secure_1psidts: str = "",
        client_factory: Callable[..., Any] | None = None,
        recent_chats: int = 20,
    ) -> None:
        self.secure_1psid = secure_1psid or os.getenv("SECURE_1PSID", "")
        self.secure_1psidts = secure_1psidts or os.getenv("SECURE_1PSIDTS", "")
        self._client_factory = client_factory
        self.recent_chats = max(13, min(int(recent_chats), 100))
        self._client: Any = None
        self._chat: Any = None

    async def connect(self) -> None:
        """Initialize the authenticated web client and its conversation."""
        if self._chat is not None:
            return
        if not self.secure_1psid:
            raise RuntimeError(
                "Gemini Web Chat credentials are missing. Set SECURE_1PSID "
                "in your environment or .env file. SECURE_1PSIDTS is optional."
            )
        factory = self._client_factory
        if factory is None:
            try:
                from gemini_webapi import GeminiClient
            except ImportError as exc:
                raise RuntimeError(
                    "gemini-webapi is not installed. Run: pip install -r requirements.txt"
                ) from exc
            factory = GeminiClient
        client = factory(self.secure_1psid, self.secure_1psidts)
        try:
            await client.init(timeout=45, auto_refresh=True)
            refresh_recent = getattr(client, "_fetch_recent_chats", None)
            if refresh_recent is not None:
                await refresh_recent(recent=self.recent_chats)
            chat = client.start_chat()
        except Exception as exc:
            raise ConnectionError(f"Could not connect to Gemini Web Chat: {exc}") from exc
        self._client, self._chat = client, chat

    def list_chats(self) -> list[Any]:
        """Return recent Gemini conversations loaded during client initialization."""
        if self._client is None:
            raise RuntimeError("Connect before listing conversations.")
        return list(self._client.list_chats() or [])

    def list_models(self) -> list[Any]:
        """Return models discovered for the authenticated account."""
        if self._client is None:
            raise RuntimeError("Connect before listing models.")
        return list(self._client.list_models() or [])

    async def list_gems(self) -> list[Any]:
        """Fetch and return the account's visible Gemini Gems."""
        if self._client is None:
            raise RuntimeError("Connect before listing Gems.")
        gems = await self._client.fetch_gems(include_hidden=False, language="en")
        try:
            return list(gems)
        except TypeError:
            return list(getattr(gems, "items", ()) or ())

    async def create_gem(self, name: str, prompt: str, description: str = "") -> Any:
        if self._client is None:
            raise RuntimeError("Connect before managing Gems.")
        return await self._client.create_gem(name=name, prompt=prompt, description=description)

    async def update_gem(
        self, gem_id: str, name: str, prompt: str, description: str = ""
    ) -> Any:
        if self._client is None:
            raise RuntimeError("Connect before managing Gems.")
        return await self._client.update_gem(
            gem=gem_id, name=name, prompt=prompt, description=description
        )

    async def delete_gem(self, gem_id: str) -> None:
        if self._client is None:
            raise RuntimeError("Connect before managing Gems.")
        await self._client.delete_gem(gem_id)

    async def resume_conversation(self, cid: str) -> None:
        """Resume a remote conversation using its latest turn metadata."""
        await self.connect()
        try:
            history = await self._client.read_chat(cid, limit=1)
            turns = getattr(history, "turns", ()) if history else ()
            latest_output = next(
                (getattr(turn, "model_output", None) for turn in turns
                 if getattr(turn, "role", None) == "model"
                 and getattr(turn, "model_output", None) is not None),
                None,
            )
            metadata = getattr(latest_output, "metadata", None)
            candidates = getattr(latest_output, "candidates", ()) or ()
            rcid = getattr(candidates[0], "rcid", None) if candidates else None
            if not metadata or len(metadata) < 2 or not rcid:
                raise RuntimeError(
                    "Gemini did not return resumable metadata for this conversation."
                )
            self._chat = self._client.start_chat(
                metadata=[metadata[0], metadata[1], rcid]
            )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise ConnectionError(f"Could not resume Gemini conversation: {exc}") from exc

    async def ask(self, prompt: str) -> str:
        """Send a prompt and return Gemini's complete response."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")
        await self.connect()
        try:
            response = await self._chat.send_message(prompt)
        except Exception as exc:
            raise ConnectionError(f"Gemini Web Chat request failed: {exc}") from exc
        response_text = getattr(response, "text", None)
        return response_text if response_text is not None else str(response)

    async def new_conversation(self, model: Any = None, gem: Any = None) -> None:
        """Start a new remote conversation with optional model and Gem settings."""
        await self.connect()
        options = {}
        if model is not None:
            options["model"] = model
        if gem is not None:
            options["gem"] = gem
        self._chat = self._client.start_chat(**options)

    async def ask_stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield response chunks when the web library supports streaming."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")
        await self.connect()
        streamer = getattr(self._chat, "send_message_stream", None)
        if streamer is None:
            yield await self.ask(prompt)
            return
        try:
            async for chunk in streamer(prompt):
                if isinstance(chunk, str):
                    text = chunk
                else:
                    text = getattr(chunk, "text_delta", None)
                    if text is None:
                        text = getattr(chunk, "text", "")
                if text:
                    yield text
        except Exception as exc:
            raise ConnectionError(f"Gemini Web Chat stream failed: {exc}") from exc

    async def close(self) -> None:
        """Close the transport if the installed library exposes a close method."""
        if self._client is None:
            return
        closer = getattr(self._client, "close", None)
        if closer is not None:
            result = closer()
            if inspect.isawaitable(result):
                await result
        self._client = self._chat = None

