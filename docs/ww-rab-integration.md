# WW + RAB integrated runtime

## Ownership

- **WW owns agent work:** conversation identity, model/tool loop, workspace, approval decisions, and task outcome.
- **RAB owns device operations:** Android capability discovery, allowlisted device commands, action ledger, evidence and verification.
- **The RAB console is an observer/control surface**, not a second agent runtime. It mirrors WW task events and RAB action evidence.
- **The native RAB APK owns overlay mechanics** (window lifecycle, drag, resize, docking and persistence). Its embedded WebView owns console presentation.
- **MacroDroid owns the Android-side execution adapter**. The separate WW Android WebView remains a client of the WW API.

## Local ports

| Service | Bind | Port | Owner |
|---|---|---:|---|
| MacroDroid HTTP bridge | 127.0.0.1 | 8080 | MacroDroid |
| WW API | 127.0.0.1 | 8081 | WW |
| RAB console + SSE | 127.0.0.1 | 8765 | RAB |

All three are loopback-only. Do not expose them directly to the public internet.

## Implemented in this integration

1. WW terminal and browser tasks publish task lifecycle and tool events to RAB.
2. RAB health polling checks the exact MacroDroid RAB_PING_OK acknowledgement every ten seconds. Unknown/unreachable is not shown as healthy.
3. WW exposes rab_device_action to the model through its shared tool registry. It is allowlisted and classified as execution-risk, so it requires the existing local approval path. The browser remote read-only tool endpoint does not expose it.
4. RAB bridge acknowledgement is checked. HTTP success without the expected operation-specific response is not treated as success.
5. WW uses port 8081 so MacroDroid retains its documented port 8080. The Termux service wrapper is scripts/ww-api (start/stop/status).

The publisher is best-effort: a missing RAB console must never fail or delay an agent task beyond a short loopback timeout.

## Event contract

The publisher mirrors task start and completion/failure; tool start and tool result; local approval waits; execution limits; concise event summaries and action progress.

WW remains the source of truth. RAB display state is a projection and can be rebuilt from WW events. Device actions are not marked verified merely because MacroDroid accepted a request.

## Next implementation stages

1. **Bridge activation:** import the current localhost-only MacroDroid macro, enable the HTTP server and accessibility service, then verify ping, screenshot and one harmless UI action.
2. **Evidence pipeline:** attach screenshot IDs, timestamps, dimensions and hashes to each RAB action record. Separate dispatched, acknowledged, executed and visually verified.
3. **Approval UX:** surface pending WW approval requests in RAB, with explicit approve/deny and a short-lived action token. No approval is inferred from a tap elsewhere.
4. **Unified timeline:** correlate WW task ID, conversation ID, RAB action ID and MacroDroid request ID. Add retries/idempotency and duplicate-event protection.
5. **Recovery:** heartbeat expiry, stale-task reconciliation, bridge reconnect and explicit interrupted/unknown states. Never convert an unknown result into success.
6. **APK/scene convergence:** retain the native overlay for window management; use the embedded WebView for console UI. Keep the MacroDroid action-status popup as a transient execution notification only, with an X that hides notifications without terminating WW, RAB or VNC.

## Operational acceptance

- WW /api/v1/health and /api/v1/runtime respond on 8081 with API-key authentication.
- RAB /api/state and /events respond on 8765.
- MacroDroid /rab/ping returns exactly RAB_PING_OK on 8080.
- A terminal task and a browser task each appear in RAB with tool lifecycle transitions.
- A denied action never reaches MacroDroid.
- An acknowledged action is not marked visually verified until independent device-state evidence exists.
- Closing the RAB overlay does not stop either runtime or disconnect the remote desktop.
