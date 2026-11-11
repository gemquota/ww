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
    ) -> None:
        self.secure_1psid = secure_1psid or os.getenv("SECURE_1PSID", "")
        self.secure_1psidts = secure_1psidts or os.getenv("SECURE_1PSIDTS", "")
        self._client_factory = client_factory
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
            chat = client.start_chat()
        except Exception as exc:
            raise ConnectionError(f"Could not connect to Gemini Web Chat: {exc}") from exc
        self._client, self._chat = client, chat

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

    async def new_conversation(self) -> None:
        """Start a new remote conversation without reauthenticating."""
        await self.connect()
        self._chat = self._client.start_chat()

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

