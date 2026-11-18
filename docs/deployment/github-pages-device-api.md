# GitHub Pages frontend with a device-hosted WW API

WW can serve its browser interface from GitHub Pages while the FastAPI backend
runs on your Android device in Termux. Pages hosts only the static frontend;
the device continues to own Gemini credentials, sessions and API execution.

## 1. Enable GitHub Pages

In the repository settings, open **Pages** and set **Build and deployment** to
**GitHub Actions**. The workflow in `.github/workflows/pages.yml` publishes
`src/dashboard/chat.html` as the Pages site's `index.html`.

For this repository the expected origin is:

`https://gemquota.github.io`

The page URL is normally:

`https://gemquota.github.io/ww/`

## 2. Install and start the WW API in Termux

From the WW repository:

```bash
python -m pip install -r requirements.txt
python -m pip install fastapi uvicorn
```

Set an API key and the exact Pages origin before starting the server:

```bash
export WW_DASHBOARD_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export WW_CORS_ORIGINS="https://gemquota.github.io"
uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8080
```

Keep the generated API key private. Paste it into the browser frontend's API
key field. The frontend stores the URL and key in that tab's session storage,
not in the repository.

The API binds to loopback so it is not exposed directly to your Wi-Fi or mobile
network. Put an HTTPS tunnel or trusted VPN endpoint in front of
`http://127.0.0.1:8080` if the browser is not running on the same device.

## 3. Make the device reachable from the browser

A GitHub Pages site is HTTPS. Browsers block its JavaScript from calling an
ordinary HTTP LAN address as mixed content. For access outside the device,
use an HTTPS tunnel (for example, a Cloudflare Tunnel) or a VPN product that
provides an HTTPS endpoint. Point the frontend's **WW API URL** field at that
HTTPS endpoint, without a trailing slash.

If you use a different frontend domain, set `WW_CORS_ORIGINS` to a
comma-separated list of exact origins, for example:

```bash
export WW_CORS_ORIGINS="https://gemquota.github.io,https://chat.example.com"
```

An origin contains scheme, hostname and optional port, but no path. Do not use
`*`: the backend explicitly rejects wildcard CORS configuration.

## 4. Connect

Open the Pages URL, enter the HTTPS API URL and the API key, then press
**Connect**. The page checks `/api/v1/health`. Send a message after the status
shows a successful connection.

## Security notes

- `WW_DASHBOARD_API_KEY` is mandatory for the health check, chat and protected
  endpoints. If it is missing, protected routes fail closed with HTTP 503.
- For zero-downtime key rotation, set `WW_DASHBOARD_API_KEYS` to a comma-separated overlap of active keys, deploy/restart WW, update browser clients to the new key, then remove the old key. The legacy singular `WW_DASHBOARD_API_KEY` remains accepted.
- The browser sends the API key with its health check, so a successful
  connection confirms both reachability and authentication.
- CORS is a browser-origin policy, not authentication. The API key is still
  required for protected endpoints.
- Do not commit API keys, Gemini cookies, tunnel credentials or `.env` files.
- A public tunnel makes the API internet-reachable. Use a strong key, keep the
  device and WW dependencies updated, and stop the tunnel when not needed.
- Mobile networks and battery optimisation can interrupt a device-hosted
  backend. The Pages frontend remains available but cannot chat while the
  device or tunnel is offline.


## Remote tool safety defaults

The dashboard API now fails closed if `WW_DASHBOARD_API_KEY` is missing. Set a long random key before starting the server; protected routes return HTTP 503 until it is configured and HTTP 401 for missing or incorrect client keys.

Remote tool execution is disabled by default. To enable the restricted browser tool endpoint, set:

```bash
export WW_REMOTE_TOOLS_ENABLED=1
```

Even when enabled, the browser API exposes only `read_file` and `list_dir`, both confined to the configured WW workspace. Shell execution, Git mutations, file writes, patching, arbitrary code search and URL fetching are deliberately not exposed through the browser API. The local terminal tool workflow is unchanged.

Do not treat the API key or CORS as a sandbox. Keep the server bound to loopback and use an authenticated private tunnel for remote access. The in-memory rate limit is per observed client address; tunnel deployments may cause multiple users to share the same observed address.
- Browser chat sessions are kept in a bounded in-memory store (64 sessions by default) and expire after 30 minutes of inactivity. Requests within one tab/session are serialized; active sessions are never evicted to make room. Restarting WW clears these in-memory sessions.
- Rate limiting uses the direct TCP peer address by default and ignores `X-Forwarded-For`. If WW is behind a reverse proxy, configure `WW_TRUSTED_PROXY_CIDRS` with only the proxy IPs/CIDRs you control (comma-separated). Forwarded addresses are considered only when the immediate peer is in that trust list. Never trust all networks or accept forwarded headers directly from arbitrary clients.
