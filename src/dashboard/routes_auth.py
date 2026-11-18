"""Authentication and request controls for the WW dashboard API."""
from __future__ import annotations

import hmac
import ipaddress
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
    """Require a configured key and compare against active keys without early exit.

    WW_DASHBOARD_API_KEYS supports overlap during rotation; the singular
    WW_DASHBOARD_API_KEY remains supported for existing installations.
    """
    configured = os.getenv("WW_DASHBOARD_API_KEYS", "").strip()
    if configured:
        expected_keys = [
            value.strip()
            for value in configured.split(",")
            if value.strip()
        ]
    else:
        legacy_key = os.getenv("WW_DASHBOARD_API_KEY", "").strip()
        expected_keys = [legacy_key] if legacy_key else []

    if not expected_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WW API authentication is not configured. Set WW_DASHBOARD_API_KEY or WW_DASHBOARD_API_KEYS.",
        )

    supplied = api_key or ""
    matched = False
    for expected in expected_keys:
        matched = hmac.compare_digest(supplied, expected) or matched
    if not matched:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return supplied


def _trusted_proxy_networks():
    """Parse explicitly trusted reverse-proxy CIDRs; forwarding headers are ignored otherwise."""
    networks = []
    for value in os.getenv("WW_TRUSTED_PROXY_CIDRS", "").split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            # Invalid trust configuration must not expand the trusted boundary.
            continue
    return networks


def _client_address(request) -> str:
    peer_text = request.client.host if request.client else "unknown"
    try:
        peer = ipaddress.ip_address(peer_text)
    except ValueError:
        return peer_text

    trusted = _trusted_proxy_networks()
    if not any(peer in network for network in trusted):
        return peer.compressed

    forwarded = request.headers.get("x-forwarded-for", "")
    candidates = []
    for value in forwarded.split(",")[-16:]:
        try:
            candidates.append(ipaddress.ip_address(value.strip()))
        except ValueError:
            return peer.compressed

    # Walk from the immediate proxy toward the client. Stop at the first
    # address not explicitly trusted, preventing spoofed leftmost entries.
    current = peer
    for candidate in reversed(candidates):
        if not any(current in network for network in trusted):
            break
        current = candidate
    return current.compressed


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

    client_ip = _client_address(request)
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
