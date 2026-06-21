"""
Python SDK for programmatic bridge usage.
Addresses V4-I4: Python SDK
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional


class WWClient:
    """Programmatic client for WW Bridge.
    
    Usage:
        async with WWClient(api_key="...") as bridge:
            result = await bridge.ask("List files")
    """
    
    def __init__(
        self,
        api_key: str = "",
        secure_1psid: str = "",
        secure_1psidts: str = "",
        workspace: str = ".",
        verbose: bool = False,
    ):
        self.api_key = api_key
        self.secure_1psid = secure_1psid
        self.secure_1psidts = secure_1psidts
        self.workspace = workspace
        self.verbose = verbose
        self._client = None
        self._chat = None
    
    async def __aenter__(self) -> "WWClient":
        from src.core.utils.web_client import WebGeminiClient
        import os
        os.environ.setdefault("SECURE_1PSID", self.secure_1psid)
        os.environ.setdefault("SECURE_1PSIDTS", self.secure_1psidts)
        os.environ.setdefault("GEMINI_API_KEY", self.api_key)
        
        self._client = WebGeminiClient(
            secure_1psid=self.secure_1psid,
            secure_1psidts=self.secure_1psidts,
            api_key=self.api_key,
        )
        if not await self._client.init():
            raise RuntimeError("Failed to initialize Gemini client")
        self._chat = self._client.chat
        return self
    
    async def __aexit__(self, *args) -> None:
        pass
    
    async def ask(self, prompt: str) -> Optional[str]:
        """Send a prompt and get a response."""
        if self._client:
            return await self._client.ask(prompt)
        return None
    
    async def ask_stream(self, prompt: str) -> AsyncIterator[str]:
        """Send a prompt and stream the response."""
        if self._client:
            async for chunk in self._client.ask_stream(prompt):
                yield chunk
