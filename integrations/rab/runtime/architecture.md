# RAB architecture

RAB is a persistent execution core with ChatGPT acting as the reasoning/orchestration layer.

## Components
- **Introspector** (discover.py): probes installed commands, Android packages, external sessions and the local MacroDroid HTTP bridge.
- **Registry** (store.py): stores the JSON capability manifest and SQLite event, execution and objective ledgers.
- **Planner** (planner.py): maps supported goals to capability-aware plans. Unknown goals remain unmapped rather than guessed.
- **Factory** (factory.py): registers declarative capability artifacts against an adapter allowlist and known dependency graph.
- **Runtime** (runtime.py): invokes explicit local adapters only. It never executes arbitrary model-generated shell.
- **Agent** (agent.py): accepts objectives, persists plans, runs supported local steps and reconciles plans when capabilities change.

## Android execution path
The MacroDroid HTTP Server Trigger runs locally on the device. RAB calls the configured localhost port with allowlisted endpoint paths and query parameters. MacroDroid executes the matching action and returns a response after the action block. The HTTP trigger IP whitelist is restricted to 127.0.0.1.

## State semantics
- unavailable: required dependency or execution path is missing.
- discovered: an item was observed but has not been shown executable.
- executable: an execution path exists; outcome is not independently verified.
- verified: direct evidence supports the capability claim.
- awaiting_setup: artifact exists, but a user-controlled import, permission or server step remains.

Execution and verification are distinct. A successful HTTP response is recorded as accepted/executed, not as proof that every external effect occurred.

## Replay and permissions
- Events are content-addressed by default and inserted with INSERT OR IGNORE.
- Executions accept stable operation IDs; replay returns the stored result rather than repeating the side effect.
- Objectives have stable IDs and can be reconciled when the capability graph changes.
- Capability registration rejects unknown adapters and dependencies.
- A capability that requires new permissions cannot be registered as executable before approval.
