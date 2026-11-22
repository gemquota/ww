# Recursive Agent Bootstrap (RAB)

A persistent, capability-driven agent runtime for Termux.

## Principles
- Discover before assuming.
- Distinguish discovered, executable, and verified capabilities.
- Compose only registered adapters; never turn model output into arbitrary shell.
- Persist capability state and execution evidence outside the conversation.
- Reconcile repeated information idempotently.
- Capability expansion never silently expands permissions.

## Commands
- python -m rab.cli discover: refresh the local capability manifest.
- python -m rab.cli manifest: print the current manifest.
- python -m rab.cli status: report runtime and capability state.
- python -m rab.cli validate: run non-destructive capability checks.
- python -m rab.cli goal "...": persist an objective and produce a capability-aware plan.
- python -m rab.cli run OBJECTIVE_ID: execute supported local plan steps.
- python -m rab.cli reconcile: replan outstanding objectives after capability changes.
- python -m rab.cli objectives: list persisted objectives.
- python -m rab.cli graph: print capability dependencies.
- python -m rab.cli bridge-probe: test the localhost MacroDroid bridge.
- python -m rab.cli bridge-config --port 8080: configure its HTTP port.
- python -m rab.cli bridge OPERATION: invoke a registered bridge operation.

No third-party Python dependencies are required.

## Safety and state model
Capability states are deliberately non-interchangeable:
- unavailable: required executable, companion app, or session is missing.
- executable: an execution path exists, but end-to-end behavior is not yet proven.
- verified: a probe produced direct evidence for the stated capability.
- awaiting_setup: an artifact exists, but a user-controlled import, permission, or server setup step remains.

Execution adapters are explicit and allowlisted. The runtime does not accept arbitrary shell strings from a plan. Supply a stable operation ID when replay protection is required; the execution ledger returns the prior result instead of repeating that operation.

## Android bridge
The RAB Local Android Bridge is one MacroDroid macro with seven localhost-only HTTP endpoints: notification, screenshot, tap, drag, text entry, app launch, and health check. It restricts incoming requests to 127.0.0.1. MacroDroid's HTTP server port is configured in its settings; RAB defaults to 8080 and can be reconfigured.

The macro must be imported and enabled once. MacroDroid's HTTP server must be running. Screen capture and UI interaction require MacroDroid's accessibility service. The bridge is not marked executable until the local health endpoint responds correctly.

See MANIFEST.md for the generated capability snapshot and docs/architecture.md for the state model.
