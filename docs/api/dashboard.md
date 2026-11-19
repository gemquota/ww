# Local dashboard API

The dashboard is a local FastAPI client for the shared `ConversationRuntime`. It uses the same `WWClient`, tool registry, schema validation, approval controller and feedback loop as the terminal.

Start it from the repository root:

```bash
python -m pip install -r requirements-dashboard.txt
uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8080
```

The server binds to loopback by default. Protected endpoints require `X-API-Key`, configured through `WW_DASHBOARD_API_KEY` or the active key list `WW_DASHBOARD_API_KEYS`. CORS defaults to the GitHub Pages origin and can be overridden with an explicit comma-separated `WW_CORS_ORIGINS` list. Wildcard CORS is rejected.

## Supported browser endpoints

| Method | Path | Purpose | Authentication |
|---|---|---|---|
| GET | `/` | API metadata | No |
| GET | `/chat-ui` | Serve the browser workspace | No |
| GET | `/api/v1/health` | Backend and local database health | API key |
| GET | `/api/v1/runtime` | Workspace, Python, backend and credential readiness | API key |
| POST | `/api/v1/chat/stream` | Streaming chat and tool lifecycle events (SSE) | API key |
| POST | `/chat` | Non-streaming compatibility chat | API key |
| POST | `/tools/execute` | Direct read-only tool call | API key + opt-in |

The API also retains telemetry compatibility routes for listing sessions and statistics. They are not required by the current browser workspace.

## Streaming request

```http
POST /api/v1/chat/stream
Content-Type: application/json
X-API-Key: <local-api-key>
```

```json
{
  "message": "Inspect the README and summarize the project",
  "session_name": "browser-session-id",
  "conversation_id": null
}
```

The response is an SSE stream with JSON `data:` events. Event types include model text deltas, tool start, approval required, tool result, tool-round completion, final completion and error. Tool calls are executed by the shared runtime; they are not executed in the browser.

## Tool execution policy

- Read-only inspection tools can run without an approval prompt.
- File writes, patches, Git mutations and shell commands require local approval in the backend terminal.
- The backend must have interactive stdin for this approval flow.
- The direct `/tools/execute` endpoint is disabled by default. When enabled, it still allows only `read_file` and `list_dir`.
- URL fetching is not registered because safe DNS pinning and redirect validation are not yet implemented.

## Session lifecycle

Browser sessions are stored in a bounded in-memory session store. The frontend persists Gemini conversation IDs and can resume them after backend session eviction or restart. The frontend's local transcript is separate from Gemini's cloud conversation history.

## Health and deployment

The unauthenticated root route returns static API metadata and is suitable for a container liveness check. The detailed health and runtime endpoints remain authenticated.

For GitHub Pages and Termux/PRoot setup, see [the device-hosted API deployment guide](../deployment/github-pages-device-api.md).
