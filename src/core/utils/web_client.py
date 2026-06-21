from pathlib import Path
"""Clean Gemini Web API client abstraction with retry logic."""
import os
import time
import asyncio
from typing import Optional, AsyncIterator, Dict, Any, List, Tuple, Callable
from loguru import logger
from gemini_webapi import GeminiClient
class CircuitBreaker:
    """Circuit breaker for API calls with three states: Closed, Open, Half-Open."""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    @property
    def state(self) -> str:
        if self._state == "OPEN" and (time.time() - self._last_failure_time) > self.recovery_timeout:
            self._state = "HALF_OPEN"
        return self._state
    
    def record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"
    
    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")
    
    def can_proceed(self) -> bool:
        state = self.state
        if state == "CLOSED":
            return True
        if state == "HALF_OPEN":
            return True  # Allow probe request
        return False  # OPEN — reject


class WebGeminiClient:
    """Reusable Gemini Web API client with retry, rate limiting, and streaming."""

    def __init__(self, secure_1psid: str = "", secure_1psidts: str = "",
                 rate_limit_rpm: Optional[int] = None, api_key: str = ""):
        self.secure_1psid = secure_1psid
        self.secure_1psidts = secure_1psidts
        self.api_key = api_key
        self.client: Optional[GeminiClient] = None
        self.chat = None
        self._use_api_key = False
        self._circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        # Rate limiting
        self._request_times: list = []
        self._rate_limit_rpm = rate_limit_rpm or self._get_config_rate_limit()
        self._rate_lock = asyncio.Lock()

    @staticmethod
    def _get_config_rate_limit() -> int:
        """Read rate limit from config, falling back to environment."""
        try:
            from src.config import get_settings
            return get_settings().gemini.rate_limit_rpm
        except Exception:
            try:
                return int(os.getenv("WW_GEMINI__RATE_LIMIT_RPM", "10"))
            except (ValueError, TypeError):
                return 10

    async def _check_rate_limit(self):
        """Enforce rate limit — pause if we've exceeded RPM budget."""
        async with self._rate_lock:
            now = time.time()
            window_start = now - 60
            self._request_times = [t for t in self._request_times if t > window_start]
            if len(self._request_times) >= self._rate_limit_rpm:
                sleep_for = self._request_times[0] - window_start
                if sleep_for > 0:
                    logger.warning(f"Rate limit: sleeping {sleep_for:.1f}s")
                    await asyncio.sleep(sleep_for)
                self._request_times = [t for t in self._request_times if t > (time.time() - 60)]
            self._request_times.append(now)

    async def init(self) -> bool:
        if self.client:
            return True
        
        # Priority 1: Cookie-based auth (default unless WW_USE_API is set)
        use_api_env = os.getenv("WW_USE_API", "false").lower() == "true"
        
        if self.secure_1psid and self.secure_1psidts and not use_api_env:
            try:
                self.client = GeminiClient(self.secure_1psid, self.secure_1psidts)
                await self.client.init(timeout=45, auto_refresh=True)
                self.chat = self.client.start_chat()
                self._use_api_key = False
                logger.info("Initialized Gemini via Web Cookies")
                return True
            except Exception as e:
                logger.warning(f"Cookie auth failed, falling back to API key if available: {e}")

        # Priority 2: API key auth (explicit or fallback)
        api_key = self.api_key
        if api_key:
            try:
                import google.genai as genai
                genai_client = genai.Client(api_key=api_key)
                # Test the connection with a simple request
                resp = genai_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents="Respond with only the word OKAY."
                )
                if resp and hasattr(resp, 'text') and 'OKAY' in resp.text:
                    self.client = genai_client
                    self._use_api_key = True
                    logger.info("Initialized Gemini via API key")
                    return True
            except Exception as e:
                logger.warning(f"API key auth failed: {e}")
        
        # Fallback to cookies if API key failed but we didn't try cookies yet
        if self.secure_1psid and self.secure_1psidts and not self.client:
            try:
                self.client = GeminiClient(self.secure_1psid, self.secure_1psidts)
                await self.client.init(timeout=45, auto_refresh=True)
                self.chat = self.client.start_chat()
                self._use_api_key = False
                logger.info("Initialized Gemini via Web Cookies (fallback)")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Web Client: {e}")
                self.client = None
                return False

        logger.error("No valid credentials found or initialization failed.")
        return False

    async def ask(self, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Send a message with rate limiting, circuit breaker, and exponential backoff retry.
        
        Returns the full response text, or None on failure.
        Supports both API key (google.genai) and cookie-based (gemini_webapi) auth.
        """
        if not await self.init():
            return None
        
        # Circuit breaker check
        if not self._circuit_breaker.can_proceed():
            logger.warning("Circuit breaker OPEN — rejecting request")
            return None
        
        await self._check_rate_limit()
        
        # API key path — use google.genai directly
        if getattr(self, '_use_api_key', False):
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                    if hasattr(response, 'text'):
                        self._circuit_breaker.record_success()
                        return response.text
                    self._circuit_breaker.record_success()
                    return str(response)
                except Exception as e:
                    self._circuit_breaker.record_failure()
                    wait = (2 ** attempt) + 1
                    logger.warning(f"Gemini API Error (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"Max retries reached: {e}")
                        return None
        
        # Cookie-based path
        for attempt in range(max_retries):
            try:
                response = await self.chat.send_message(prompt)
                res_text = response.text if hasattr(response, 'text') else str(response)
                self._circuit_breaker.record_success()
                return res_text
            except Exception as e:
                self._circuit_breaker.record_failure()
                wait = (2 ** attempt) + 1
                logger.warning(f"Gemini Web Error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Max retries reached: {e}")
                    return None

    async def ask_stream(self, prompt: str, max_retries: int = 3) -> AsyncIterator[str]:
        """Send a message and yield response chunks as they arrive (streaming).
        
        Supports both API key and cookie-based auth.
        Falls back to yielding the full response as a single chunk if streaming
        is not available.
        
        Yields:
            str: Text chunks as they arrive from the model.
        """
        if not await self.init():
            yield "ERROR: Gemini client not initialized."
            return

        await self._check_rate_limit()
        
        # API key path
        if getattr(self, '_use_api_key', False):
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt
                    )
                    yield response.text if hasattr(response, 'text') else str(response)
                    return
                except Exception as e:
                    wait = (2 ** attempt) + 1
                    logger.warning(f"Gemini API Error (attempt {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait)
                    else:
                        yield f"ERROR: {e}"
                        return

        for attempt in range(max_retries):
            try:
                # Try streaming if the API supports it
                if hasattr(self.chat, 'send_message_stream'):
                    async for chunk in self.chat.send_message_stream(prompt):
                        if chunk:
                            yield chunk
                else:
                    # Fallback to non-streaming
                    response = await self.chat.send_message(prompt)
                    yield response.text if hasattr(response, 'text') else str(response)
                return
            except Exception as e:
                wait = (2 ** attempt) + 1
                logger.warning(f"Gemini Web Stream Error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait)
                else:
                    yield f"ERROR: {e}"
                    return


_global_client = None

async def get_web_client(secure_1psid: str = "", secure_1psidts: str = "") -> WebGeminiClient:
    global _global_client
    if _global_client is None:
        _global_client = WebGeminiClient(secure_1psid=secure_1psid, secure_1psidts=secure_1psidts)
        await _global_client.init()
    return _global_client


# ── Merged from api_keys.py (# API key management) ──
class APIKeyManager:
    """SQLite-backed API key store with create/rotate/revoke."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_table()

    def _init_table(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT UNIQUE NOT NULL,
                    prefix TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT 'default',
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    revoked INTEGER DEFAULT 0,
                    last_used_at REAL,
                    permissions TEXT DEFAULT 'read'
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def create_key(self, name: str = "default",
                   expires_in_days: Optional[int] = None,
                   permissions: str = "read") -> Dict[str, Any]:
        """Create a new API key. Returns the full key (only shown once)."""
        prefix = "ww_" + secrets.token_hex(4)
        key = prefix + "_" + secrets.token_hex(24)
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        expires_at = (time.time() + expires_in_days * 86400) if expires_in_days else None

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "INSERT INTO api_keys (key_hash, prefix, name, created_at, expires_at, permissions) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key_hash, prefix, name, time.time(), expires_at, permissions)
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "key": key,
            "prefix": prefix,
            "name": name,
            "created_at": time.time(),
            "expires_at": expires_at,
            "permissions": permissions,
            "warning": "Store this key securely. It will not be shown again."
        }

    def validate_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key. Returns key info or None."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT id, prefix, name, created_at, expires_at, revoked, permissions "
                "FROM api_keys WHERE key_hash = ?", (key_hash,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            key_id, prefix, name, created_at, expires_at, revoked, permissions = row

            if revoked:
                return None
            if expires_at and time.time() > expires_at:
                return None

            # Update last used
            conn.execute("UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                         (time.time(), key_id))
            conn.commit()

            return {
                "id": key_id,
                "prefix": prefix,
                "name": name,
                "created_at": created_at,
                "expires_at": expires_at,
                "permissions": permissions,
            }
        finally:
            conn.close()

    def revoke_key(self, prefix: str) -> bool:
        """Revoke a key by its prefix."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "UPDATE api_keys SET revoked = 1 WHERE prefix = ?", (prefix,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_keys(self) -> list:
        """List all non-revoked keys (without the secret)."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT prefix, name, created_at, expires_at, last_used_at, permissions "
                "FROM api_keys WHERE revoked = 0 ORDER BY created_at DESC"
            )
            return [dict(zip(["prefix", "name", "created_at", "expires_at",
                              "last_used_at", "permissions"], row))
                    for row in cursor.fetchall()]
        finally:
            conn.close()
