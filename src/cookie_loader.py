"""Read Gemini session cookies from a Netscape-format cookies.txt file.

The primary session cookie must be scoped to google.com. Google also exports
the timestamp cookie on youtube.com in some browser profiles, so that one
additional Google-owned domain is accepted for __Secure-1PSIDTS only. Values
are returned to the caller and are never logged.
"""
from __future__ import annotations

import http.cookiejar
import os
from pathlib import Path
from typing import MutableMapping


COOKIE_NAMES = ("__Secure-1PSID", "__Secure-1PSIDTS")


def extract_gemini_cookies(path: str | Path) -> dict[str, str]:
    """Extract the two Gemini session cookies from a Netscape cookie jar.

    Returns an empty dict when the file does not exist. The primary
    __Secure-1PSID cookie is required by the caller; __Secure-1PSIDTS remains
    optional for accounts or exports that do not contain it.
    """
    cookie_path = Path(path).expanduser()
    if not cookie_path.is_file():
        return {}

    jar = http.cookiejar.MozillaCookieJar(str(cookie_path))
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
    except (http.cookiejar.LoadError, OSError) as exc:
        raise ValueError(
            f"Could not read {cookie_path}. Expected a Netscape-format cookies.txt file."
        ) from exc

    found: dict[str, str] = {}
    for cookie in jar:
        domain = cookie.domain.lstrip(".").lower()
        google_domain = domain == "google.com" or domain.endswith(".google.com")
        youtube_timestamp = domain == "youtube.com" and cookie.name == "__Secure-1PSIDTS"
        if not (google_domain or youtube_timestamp):
            continue
        if cookie.name in COOKIE_NAMES and cookie.value:
            found[cookie.name] = cookie.value

    result: dict[str, str] = {}
    if found.get("__Secure-1PSID"):
        result["SECURE_1PSID"] = found["__Secure-1PSID"]
    if found.get("__Secure-1PSIDTS"):
        result["SECURE_1PSIDTS"] = found["__Secure-1PSIDTS"]
    return result



def load_cookie_environment(
    path: str | Path,
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, str]:
    """Populate missing/blank Gemini cookie variables without overriding explicit values."""
    target = os.environ if environ is None else environ
    extracted = extract_gemini_cookies(path)
    for key, value in extracted.items():
        if not target.get(key):
            target[key] = value
    return extracted
