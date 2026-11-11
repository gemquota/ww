"""Minimal Gemini Web Chat transport for the WW terminal product.

This module deliberately knows nothing about agents, tools, workspaces,
or orchestration. One instance owns one Gemini Web Chat conversation.
"""
from __future__ import annotations

import inspect
import os
from typing import Any, Callable


class GeminiWebChat:
    """A small stateful client for Google's Gemini Web Chat."""

    def __init__(
        self,
        secure_1psid: str | None = None,
        secure_1psidts: str | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.secure_1psid = secure_1psid or os.getenv("SECURE_1PSID", "")
        self.secure_1psidts = secure_1psidts or os.getenv("SECURE_1PSIDTS", "")
        self._client_factory = client_factory
        self.client: Any = None
        self.chat: Any = None

    async def connect(self) -> None:
        """Authenticate and open a Gemini Web Chat conversation."""
        if self.chat is not None:
            return
        if not self.secure_1psid or not self.secure_1psidts:
            raise RuntimeError(
                "Gemini Web Chat credentials are missing. Set SECURE_1PSID "
                "and SECURE_1PSIDTS in your environment or .env file."
            )

        factory = self._client_factory
        if factory is None:
            try:
                from gemini_webapi import GeminiClient
            except ImportError as exc:
                raise RuntimeError(
                    "The Gemini Web client is not installed. Run: "
                    "python -m pip install -r requirements.txt"
                ) from exc
            factory = GeminiClient

        client = factory(self.secure_1psid, self.secure_1psidts)
        try:
            await client.init(timeout=45, auto_refresh=True)
            chat = client.start_chat()
        except Exception as exc:
            raise ConnectionError(f"Could not connect to Gemini Web Chat: {exc}") from exc

        self.client = client
        self.chat = chat

    async def send(self, prompt: str) -> str:
        """Send one prompt and return Gemini's complete response text."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must not be empty.")
        await self.connect()
        try:
            response = await self.chat.send_message(prompt)
        except Exception as exc:
            raise ConnectionError(f"Gemini Web Chat request failed: {exc}") from exc

        text = getattr(response, "text", None)
        if text is None:
            text = str(response)
        return text

    async def new_conversation(self) -> None:
        """Start a fresh remote chat while retaining the authenticated client."""
        await self.connect()
        self.chat = self.client.start_chat()

    async def close(self) -> None:
        """Close the underlying client when its library version supports it."""
        if self.client is None:
            return
        closer = getattr(self.client, "close", None)
        if closer is not None:
            result = closer()
            if inspect.isawaitable(result):
                await result
        self.client = None
        self.chat = None
