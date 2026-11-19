# Phase 2: approved and isolated tool execution

Phase 2 adds a controlled path for privileged tools without weakening the Phase 1 remote API boundary.

## Current state

The first Phase 2 commit introduces two foundations:

- `src/tools/tool_policy.py` classifies known tools by risk. Unknown tools are denied. Only `read_file` and `list_dir` are marked as remotely exposable.
- `src/tools/approvals.py` provides short-lived, one-use approval grants bound to the exact session, tool name and canonical argument digest. A grant cannot be replayed with changed arguments or in another session.
- `src/tools/local_approval.py` provides a terminal-only human approval controller. The interactive tool executor displays the exact arguments and requires an explicit `y`/`yes` decision before mutations, shell execution, Git operations or network fetches. Rejection, EOF and approval errors fail closed and immediately discard the pending request.
- `src/tools/audit.py` writes structured JSONL audit events for approval requests, decisions and execution outcomes. Records contain a canonical tool name, process-keyed HMAC fingerprints for the session and exact arguments, timestamps, decisions and outcome metadata. Fingerprints correlate events during one WW process lifetime and cannot be used for offline guessing of low-entropy arguments. Raw arguments, credentials and approval tokens are never written.
- Tool aliases are normalized before policy lookup, including the actual registry name `git`.

The approval ledger is in-memory. Pending requests expire after five minutes; approved grants expire after two minutes. Pending requests and grants are each capped at 256 records, with expired entries pruned before capacity checks. Restarting WW invalidates all pending requests and grants. The ledger is not wired to an HTTP endpoint. The local terminal is the only approval surface; browser clients cannot approve requests. The browser API remains limited to read-only tools.

The audit log defaults to `~/.ww/audit/audit.jsonl` (overridable with `WW_AUDIT_LOG`). The containing directory must be private (mode 0700), the file and lock file are forced to mode 0600, symlink and hard-link targets are rejected, and the append-only log is capped at 1 MiB. When an approval event cannot be durably recorded or the log is full, the privileged operation is denied. Archive the log before it reaches the cap with `python -m src.tools.audit archive`; archival takes the same cross-process lock as writes and starts a fresh log, leaving a timestamped private archive beside it. Export a redacted copy to a new file in a private directory with `python -m src.tools.audit export /path/to/private/audit-copy.jsonl`; exports never overwrite existing files and use mode 0600. Execution-result audit failures are reported but cannot undo an operation that has already completed.

## Required execution flow

1. The model proposes a tool call. It does not approve its own request.
2. The policy layer classifies the tool. Unknown tools fail closed.
3. Read-only tools may proceed only if they are explicitly allowed by the caller's surface.
4. A privileged tool creates a pending approval request bound to the exact arguments and session.
5. The device-local operator reviews the tool, arguments, target paths and expected effects, then approves or rejects it.
6. The runner consumes the one-use grant immediately before execution. Any argument, tool or session change invalidates the grant.
7. The runner records a redacted audit event and enforces the execution boundary.
8. Cancellation, timeout or output overflow terminates the complete process group and reaps the child.

## Isolation requirements before enabling privileged remote execution

A workspace working directory is not a sandbox. A subprocess must not be considered isolated merely because its current directory is the WW repository.

The runner must fail closed unless the host provides a verified isolation backend with:

- filesystem access limited to explicitly mounted workspace paths and temporary scratch space;
- no access to browser cookies, environment secrets, SSH material, host home directories or device control sockets;
- network disabled by default, with explicit per-tool exceptions;
- CPU, memory, process-count, file-size, descriptor and wall-clock limits applied to the child rather than the WW server;
- a fixed executable/argument policy instead of arbitrary shell interpolation wherever possible;
- bounded stdout/stderr capture, process-group termination and child reaping;
- an audit trail that records the decision and result without recording credentials or approval tokens.

The backend must be capability-detected on the actual deployment platform. Termux/proot, ordinary Linux, containers and desktop systems do not provide identical isolation primitives. If a strong backend is unavailable, privileged remote execution stays disabled.

## Delivery sequence

- **2A, policy and grants:** risk classification, one-use approval primitives and tests. Started.
- **2B, local approval UX:** implemented in the terminal executor with exact argument previews and explicit local approve/reject decisions; add richer diff previews and terminal-specific usability tests before calling it complete.
- **2C, isolated runner:** select and verify a platform-specific sandbox; enforce resource, filesystem and network boundaries.
- **2D, audit and recovery:** first audit slice implemented: durable redacted JSONL records for approval and execution lifecycle, bounded storage, restrictive file permissions, symlink/hard-link rejection and fail-closed approval when the audit sink is unavailable. Subprocess execution now shares a bounded runner for shell, Git, grep-based searches and curl fallback; timeout and cancellation terminate the process group, drain output and reap the parent. Tests exercise stubborn parent/child processes that ignore SIGTERM. Remaining work: device-side Termux verification and end-to-end failure recovery.
- **2E, remote integration:** only after 2B–2D pass, expose a narrow approval-request/status API. Approval itself remains a local device action. Shell access is not automatically granted by approving an individual operation.

## Acceptance criteria

- No privileged model-issued tool call can run without a valid one-use grant consumed immediately before execution.
- Grants are bound to the exact tool, argument digest and session, expire quickly and cannot be replayed.
- A model or remote browser client cannot approve its own request.
- No sandbox means no privileged execution.
- Read-only remote tools remain the only browser-exposed tools until the complete approval and isolation path is verified.
