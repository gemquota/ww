# WW/RAB action verification and recovery

## Purpose

Make real-device UI automation evidence-driven. A successful HTTP response is a transport acknowledgement, not proof that Android accepted an input event or reached the requested UI state.

## Current implementation

The vendored runtime is in integrations/rab/runtime/. Its SQLite store adds:

- action_records: one durable record per action ID, bound to the original capability, operation and request.
- action_evidence: append-only evidence items with source, claim, result, confidence, timestamps and optional artifact/hash references.
- Separate transport, execution and verification statuses.
- Stale-frame protection: a visual observation captured before dispatch cannot verify the action.
- Raw observations never mark an outcome verified; a registered independent verifier is not implemented yet.
- Ambiguous or stale observations remain non-success states.
- Reusing an action ID with a different request is rejected.
- Replaying an existing execution ID returns the prior result rather than repeating the side effect.

The Android bridge path now reports acknowledged rather than accepted when the bridge returns success. The record deliberately leaves execution unknown and verification pending.

## State vocabulary

- Transport: pending, acknowledged, rejected, unknown.
- Execution: unknown until there is runtime/input-subsystem evidence; a bridge response alone cannot set it to executed.
- Verification: pending, verified, not_confirmed, stale_observation, indeterminate.
- Sequence-level failure, timeout and recovery remain orchestration decisions; they must not be inferred from a stale screenshot.

## CLI

    rab action list --limit 20
    rab action show ACTION_ID
    rab action observe ACTION_ID \
      --state 'Settings screen' \
      --source Termalin-VNC \
      --match yes \
      --captured-at 1760000000.0 \
      --received-at 1760000000.2 \
      --confidence 0.95 \
      --artifact-reference frame-42

Observation timestamps are Unix seconds. captured-at must come from the capture source, not be fabricated from receipt time. The CLI's --match value is only an operator-supplied claim. It never creates a verification decision. If capture time is absent or the frame predates dispatch, the record cannot become verified. No public CLI command can currently promote an action to VERIFIED.

## Recovery invariants

1. An acknowledgement never implies execution or outcome success.
2. A timeout means confirmation is missing, not that the action failed.
3. Reconcile current device state before retrying an ambiguous action.
4. Never automatically repeat toggles or non-idempotent actions after ambiguous execution.
5. A stale or unavailable VNC frame is an observation failure, not an action failure.
6. Unexpected dialogs pause the sequence; permission/security prompts require explicit authorization.
7. Popup cleanup is isolated from RAB process lifecycle and the existing VNC session.
8. Closing the Action Viewer must not cancel an action or sequence.

## Action Viewer

Always show sequence progress, current action, transport/execution/verification distinctions, RAB/VNC connectivity and the last three meaningful events. Keep polling noise and raw diagnostics behind an expandable detail view. The close control hides the viewer only; it must not stop RAB or disconnect VNC.

## Validation

Run the vendored RAB tests:

    cd integrations/rab/runtime
    PYTHONPATH=. python -m unittest discover -s tests -v

Run WW bridge integration tests:

    cd ~/ww
    python -m unittest tests.test_rab_integration -v

A passing unit test suite validates local state and policy logic only. It does not prove end-to-end Android input injection, Termalin screenshot freshness, popup cleanup isolation, or VNC continuity. Those require a real-device acceptance run with baseline and post-cleanup process/session identifiers and a fresh visual observation.

## Remaining engineering work

- Add a trusted execution callback from the Android input adapter; do not infer injection from HTTP.
- Connect Termalin frame capture metadata directly to rab action observe, including real capture timestamps and artifact references.
- Add sequence-level deadlines, bounded observation backoff, pause/reconcile/resume and risk-class-aware retry policy.
- Add explicit interruption classification for Android permission, security, authentication, destructive and unknown dialogs.
- Add a dedicated popup-cleanup acceptance test that proves the original RAB process and VNC session remain alive and interactive.
- Wire Action Viewer events to the durable action ledger, with a close-only overlay operation.
- Implement a registered verifier authorization boundary before any action can become VERIFIED. Raw observations and verifier decisions must be separate records.
- Calibrate confidence from observed test data; current confidence values are operator-supplied evidence weights, not statistical probabilities.
