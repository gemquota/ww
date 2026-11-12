"""Read Gemini session cookies from a Netscape-format cookies.txt file.

Only cookies scoped to google.com (including its subdomains) are considered.
Cookie values are returned to the caller and are never logged.
"""
from __future__ import annotations

import http.cookiejar
from pathlib import Path


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
        if domain != "google.com" and not domain.endswith(".google.com"):
            continue
        if cookie.name in COOKIE_NAMES and cookie.value:
            found[cookie.name] = cookie.value

    result: dict[str, str] = {}
    if found.get("__Secure-1PSID"):
        result["SECURE_1PSID"] = found["__Secure-1PSID"]
    if found.get("__Secure-1PSIDTS"):
        result["SECURE_1PSIDTS"] = found["__Secure-1PSIDTS"]
    return result
