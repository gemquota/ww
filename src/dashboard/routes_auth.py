"""Authentication and rate limiting for dashboard API."""
import time as _time
from collections import defaultdict
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os

API_KEY = os.getenv("WW_DASHBOARD_API_KEY", "")
API_KEY_HEADER = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)

_rate_limit_store = defaultdict(list)
RATE_LIMIT_DEFAULT = 100  # requests/minute


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key from the X-API-Key header."""
    if API_KEY and (not api_key or api_key != API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )
    return api_key


async def rate_limit_middleware(request, call_next):
    """Rate limiting middleware: 100 req/min per IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = _time.time()
    window = 60
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < window
    ]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_DEFAULT:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded.", "retry_after": 60}
        )
    _rate_limit_store[client_ip].append(now)

    response = await call_next(request)
    response.headers["X-API-Version"] = "v1"
    return response


async def api_versioning_redirect(request, call_next):
    """Redirect /api/ -> /api/v1/."""
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/v"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=path.replace("/api/", "/api/v1/", 1))
    return await call_next(request)
