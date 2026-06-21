import os
import asyncio
from typing import Optional
from loguru import logger
from gemini_webapi import GeminiClient
from dotenv import load_dotenv

load_dotenv()

class WebGeminiClient:
    """
    Utility class to manage communication with Gemini Web.
    Encapsulates the initialization and message sending logic from gemini_bridge.py.
    """
    def __init__(self):
        self.secure_1psid = os.getenv("SECURE_1PSID")
        self.secure_1psidts = os.getenv("SECURE_1PSIDTS")
        self.client: Optional[GeminiClient] = None
        self.chat = None

    async def init(self) -> bool:
        if self.client:
            return True

        if not self.secure_1psid or not self.secure_1psidts:
            logger.error("SECURE_1PSID or SECURE_1PSIDTS not found in environment variables.")
            return False

        try:
            self.client = GeminiClient(self.secure_1psid, self.secure_1psidts)
            await self.client.init(timeout=45, auto_refresh=True)
            self.chat = self.client.start_chat()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Web Client: {e}")
            self.client = None
            return False

    async def ask(self, prompt: str, max_retries: int = 3, session_id: str = "web_default") -> Optional[str]:
        """Sends a message to Gemini and returns the response text with retry logic."""
        from core.telemetry import telemetry
        if not await self.init():
            return None

        for attempt in range(max_retries):
            try:
                response = await self.chat.send_message(prompt)
                res_text = ""
                if hasattr(response, 'text'):
                    res_text = response.text
                else:
                    res_text = str(response)
                
                telemetry.log(session_id, "web_api_call", {
                    "prompt": prompt,
                    "response": res_text,
                    "attempt": attempt + 1
                })
                return res_text
            except Exception as e:
                err_msg = str(e).lower()
                wait = (2 ** attempt) + 1
                logger.warning(f"Gemini Web Error (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Max retries reached for Gemini Web: {e}")
                    return None

# Singleton-like access if needed
_global_client = None

async def get_web_client() -> WebGeminiClient:
    global _global_client
    if _global_client is None:
        _global_client = WebGeminiClient()
        await _global_client.init()
    return _global_client
