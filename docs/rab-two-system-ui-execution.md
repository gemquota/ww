# WW -> RAB two-system UI execution

The `rab_ui_action` tool connects the Jev/Gemini decision layer to the vendored
RAB/MacroDroid bridge. It is registered in the shared terminal/browser runtime
as an execution-risk tool, so WW's device-local approval controller runs before
the function can dispatch any input. It is not exposed through the remote
read-only tool surface.

## Request contract

The tool accepts:
- `objective`: the intended UI outcome.
- `observation`: caller-supplied UI state; only app/screen/page/dialog/mode are
  forwarded to hosted decision services. Raw text, screenshots, and other fields
  are discarded before model calls.
- `candidates`: 1-12 unique candidate IDs with description, allowlisted operation,
  operation-specific parameters, and risk.

Supported UI operations are tap, drag, type, and launch_app. Parameters are
validated by the same vendored RAB bridge allowlist before reasoning begins.
Candidates cannot contain arbitrary shell or URLs. High-risk candidates are
never dispatched through this tool.

## Decision and dispatch

1. WW asks for local approval of the complete `rab_ui_action` call.
2. Jev System One proposes a candidate. Uncertain, unavailable, medium/high-risk,
   or negatively learned decisions route to Gemini System Two.
3. Both systems can select only one supplied candidate ID. System Two may abstain.
4. The selected low/medium-risk operation is dispatched once through the RAB
   runtime, which creates a durable action record and evidence entries.
5. Acknowledgement is reported as `dispatched`, not as success. Ambiguous
   transport outcomes are not automatically retried.

The RAB runtime requires `automation.rab_android_bridge` to be executable in
its capability manifest and the MacroDroid HTTP bridge to be reachable on
127.0.0.1:8080. If the macro is not imported/enabled, the service is offline,
or accessibility permissions are missing, execution fails closed. Gemini System Two uses
`WW_UI_SYSTEM2_TIMEOUT` (default 75 seconds) for its connection and reasoning
request; timeout or authentication failures also fail closed.

## Verification boundary

The current MacroDroid bridge returns operation acknowledgements, not a
screenshot payload or independent input-injection proof. RAB therefore keeps
execution unknown and verification pending. A fresh post-action observation
must be recorded separately; raw observations and operator match claims cannot
promote an action to VERIFIED. Do not automatically retry taps, toggles, text
entry, or app launches after an ambiguous transport result.

The existing RAB action ledger stores dispatch, acknowledgement, timestamps,
and evidence. This integration does not claim that the Termalin/VNC observation
capture path or an independent verifier is connected. Until that is implemented,
the tool's response explicitly preserves pending verification.

## Popup and session lifecycle

The MacroDroid status popup is a transient notification surface only. Its
dismissal must hide the popup without terminating the MacroDroid macro, WW API,
RAB runtime, or existing VNC session. The UI action controller does not call
the popup-clear operation as part of action execution or cleanup.
