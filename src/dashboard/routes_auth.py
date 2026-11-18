"""Authentication and request controls for the WW dashboard API."""
from __future__ import annotations

import hmac
import os
import time
from collections import OrderedDict, deque

from fastapi import HTTPException, Security, status
from fastapi.responses import RedirectResponse
from fastapi.security.api_key import APIKeyHeader

API_KEY_HEADER = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

RATE_LIMIT_DEFAULT = 100  # requests per minute per client address
_RATE_WINDOW_SECONDS = 60
_MAX_RATE_LIMIT_CLIENTS = 4096
_rate_limit_store: OrderedDict[str, deque[float]] = OrderedDict()
_last_prune = 0.0


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Require a configured key and compare it without timing-sensitive equality."""
    expected = os.getenv("WW_DASHBOARD_API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WW API authentication is not configured. Set WW_DASHBOARD_API_KEY.",
        )
    if not api_key or not hmac.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key


def api_versioning_redirect(request):
    """Return a redirect for legacy API paths, without dispatching the request."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/v"):
        return RedirectResponse(
            url=path.replace("/api/", "/api/v1/", 1),
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    return None


async def rate_limit_middleware(request, call_next):
    """Apply a bounded in-memory per-client sliding-window limit."""
    global _last_prune

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    entries = _rate_limit_store.get(client_ip)
    if entries is None:
        if len(_rate_limit_store) >= _MAX_RATE_LIMIT_CLIENTS:
            _rate_limit_store.popitem(last=False)
        entries = deque()
        _rate_limit_store[client_ip] = entries
    _rate_limit_store.move_to_end(client_ip)
    while entries and now - entries[0] >= _RATE_WINDOW_SECONDS:
        entries.popleft()

    if len(entries) >= RATE_LIMIT_DEFAULT:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded.", "retry_after": 60},
            headers={"Retry-After": "60"},
        )

    entries.append(now)

    # Prevent abandoned client addresses accumulating forever.
    if now - _last_prune >= _RATE_WINDOW_SECONDS:
        stale = [
            address for address, timestamps in _rate_limit_store.items()
            if not timestamps or now - timestamps[-1] >= _RATE_WINDOW_SECONDS
        ]
        for address in stale:
            _rate_limit_store.pop(address, None)
        _last_prune = now

    response = await call_next(request)
    response.headers["X-API-Version"] = "v1"
    return response


async def dispatch_request(request, call_next):
    """Apply legacy redirects or rate limiting, dispatching normal requests once."""
    redirect = api_versioning_redirect(request)
    if redirect is not None:
        return redirect
    return await rate_limit_middleware(request, call_next)
