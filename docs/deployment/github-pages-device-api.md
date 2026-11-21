# GitHub Pages frontend with a device-hosted WW API

The browser workspace is a static client. GitHub Pages serves the HTML/JavaScript; the authenticated FastAPI backend runs locally on the user's device and owns Gemini cookies, conversation sessions, workspace access, tool execution and approval.

## 1. Enable Pages

In repository Settings → Pages, select **GitHub Actions** as the deployment source. The authoritative workflow is `.github/workflows/pages.yml`; it publishes `src/dashboard/chat.html` as the site's `index.html`.

The repository URL is:

- Frontend origin: `https://gemquota.github.io`
- Page: `https://gemquota.github.io/ww/`

The `gh-pages` branch root index is also kept in sync for branch-based Pages configuration. There is no separate progress-dashboard deployment.

## 2. Install the local backend

Inside Debian PRoot-Distro, from the WW repository:

```bash
python -m pip install -r requirements-dashboard.txt
```

Put the Netscape-format `cookies.txt` in the repository root or configure `SECURE_1PSID` in a local, gitignored `.env`. `__Secure-1PSIDTS` is optional.

Configure the API key and workspace:

```bash
export WW_DASHBOARD_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export WW_WORKSPACE="$HOME/path/to/your/project"
export WW_CORS_ORIGINS="https://gemquota.github.io"
```

Keep the API key private. Do not commit `.env`, cookies, tunnel credentials or workspace state.

## 3. Start the backend

```bash
uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8080
```

The server binds to loopback by default. Keep it running in the foreground when using model-generated privileged tools: write, patch, Git mutation and shell requests display an approval prompt in the backend Termux terminal. A detached process without interactive stdin cannot provide this approval experience.

Commands execute in the environment where the backend process runs. WW does not launch or switch into PRoot itself. Start the backend inside Debian PRoot to make tool commands run inside that Debian environment. The runtime status reports `current-process`; it does not trust an environment variable to claim a PRoot backend. PRoot is a compatibility/execution environment, not a hardened security sandbox; commands have the permissions of the backend process.

## 4. Connect the browser

Open `https://gemquota.github.io/ww/`, expand **Backend connection**, set the API URL to `http://127.0.0.1:8080` when using the same device, enter `WW_DASHBOARD_API_KEY`, and connect.

The frontend checks the authenticated health and runtime endpoints. A successful backend-ready state confirms the API is reachable and credentials are configured; Gemini authentication itself is exercised on the first chat request.

For another device or network, use an HTTPS tunnel or private VPN endpoint forwarding to the loopback API. Do not expose port 8080 directly to the public internet. The Pages frontend requires HTTPS for non-loopback API URLs. For localhost and private-network URLs, the frontend sets the browser `targetAddressSpace` hint. Current Chrome versions may also display a Local Network Access permission prompt because the Pages origin is public and the backend is local; grant that permission for the site. This browser permission is separate from the WW API key and CORS checks. Grant it only to the trusted Pages origin; local-network permission is broader than access to the single WW port.

## API and trust boundaries

- `GET /api/v1/health` and `GET /api/v1/runtime` require the API key.
- `POST /api/v1/chat/stream` streams model text and tool lifecycle events using SSE.
- `POST /chat` is a non-streaming compatibility endpoint.
- `POST /tools/execute` is disabled unless `WW_REMOTE_TOOLS_ENABLED=1`; even then it exposes only read-only `read_file` and `list_dir`.
- Model-generated privileged tools use the shared ConversationRuntime and local terminal approval.
- CORS allows only explicitly configured origins. CORS is not authentication.
- After a successful connection, the browser saves the API URL and dashboard key in localStorage and restores them on later visits. The saved key is plaintext and accessible to scripts running on the Pages origin; use a trusted browser profile and clear it when finished.

The browser API does not expose a shell endpoint directly. This does not make the backend a sandbox: approved model-generated shell commands execute with the backend process's normal permissions.

## Sessions and proxying

Browser session objects are bounded and in-memory. The frontend stores Gemini conversation IDs locally and can ask the backend to resume a conversation after a session eviction or restart. The browser transcript is not a cloud backup.

The API ignores forwarded client addresses unless the immediate peer is in `WW_TRUSTED_PROXY_CIDRS`. If using a reverse proxy, trust only proxy addresses you control. Do not trust arbitrary `X-Forwarded-For` headers.

Mobile battery optimisation, network changes and tunnel restarts can interrupt a device-hosted backend. The static Pages page remains available while the backend is offline, but cannot chat until connectivity returns.
