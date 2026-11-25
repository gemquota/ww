# WW Two-System UI Controller

This stage adds a routing and experience-memory layer above Jev. It is **not an
input executor** and will not send taps/clicks/keystrokes.

- System 1: Jev's structured candidate choice.
- System 2: host-provided deliberation callback (LLM/planner). This keeps the
  reasoning model pluggable and avoids hard-coding a provider.
- Metacognition: confidence/risk escalation and repeated-failure escalation.
- Experience: local SQLite records coarse app/screen/page/dialog/mode state,
  candidate action, and outcome. It deliberately excludes screenshots and raw
  page text.

## API

Authenticated:
- `POST /api/v1/ui/controller/decide`: action candidates and sanitized UI
  observation. Returns an S1 suggestion or asks for S2 deliberation. The API
  endpoint has no S2 callback, so escalations are explicitly returned.
- `POST /api/v1/ui/controller/feedback`: record success/failure/uncertain
  outcome for a suggested candidate. This informs future routing but never
  grants execution permissions.

The standalone Python API `src.ui_controller.decide(..., system2=callback)`
accepts a host's deliberation callback. Callback must return an allowed
candidate ID. The runtime rejects invalid choices. A caller must separately
enforce risk policy, permissions, execute the action and independently verify
the result.

Data location defaults to `~/.local/share/ww/ui_controller.sqlite3`, override
with `WW_UI_CONTROLLER_DB`. Keep observation payloads minimal and redact secrets
before sending them to the hosted Jev service.
