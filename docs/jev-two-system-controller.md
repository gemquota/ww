# WW Two-System UI Controller

This stage adds a routing and experience-memory layer above Jev. It is **not an
input executor** and will not send taps/clicks/keystrokes.

- System 1: Jev's structured candidate choice.
- System 2: WW's Gemini Web Chat client performs deliberate reasoning when
  Jev is unavailable, uncertain, or overridden by negative experience. Its
  output is constrained to the supplied candidate IDs, and it can abstain.
- Metacognition: confidence/risk escalation and repeated-failure escalation.
- Experience: local SQLite records coarse app/screen/page/dialog/mode state,
  candidate action, and outcome. It deliberately excludes screenshots and raw
  page text.

## API

Authenticated:
- `POST /api/v1/ui/controller/decide`: action candidates and sanitized UI
  observation. Returns an S1 suggestion or routes escalation to Gemini S2.
  If Gemini is unavailable or abstains, the controller returns a non-executable
  escalation result.
- `POST /api/v1/ui/controller/feedback`: record success/failure/uncertain
  outcome for a suggested candidate. This informs future routing but never
  grants execution permissions.

The standalone Python API `src.ui_controller.decide(..., system2=callback)`
still accepts a custom deliberation callback. The dashboard supplies WW's
Gemini-backed implementation. Both paths must return an allowed candidate ID
or abstain; invalid choices are rejected. A caller must separately enforce
risk policy, permissions, execute the action and independently verify the
result. No device action executor is connected yet.

Data location defaults to `~/.local/share/ww/ui_controller.sqlite3`, override
with `WW_UI_CONTROLLER_DB`. Keep observation payloads minimal and redact secrets
before sending them to the hosted Jev service.
