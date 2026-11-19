# Phase 2: local approval and reliable tool execution

**Current status:** local approval, audit and bounded process execution are implemented in the shared ConversationRuntime. Android Termux/PRoot device verification remains outstanding.

## Current architecture

The supported tool path is:

`ConversationRuntime → ToolRegistry → schema validation → tool policy → LocalApprovalController → system_tools → feedback to Gemini`

- `src/tools/tool_policy.py` classifies canonical tool names and aliases. Unknown tools are denied. Only `read_file` and `list_dir` are exposed through the optional direct browser tool endpoint.
- `src/tools/args.py` defines Pydantic argument schemas. The registry validates arguments before approval or execution.
- `src/tools/local_approval.py` provides the local terminal approval controller. Privileged writes, patches, Git operations and shell commands require an explicit local decision. Rejection, EOF and approval errors fail closed.
- `src/tools/audit.py` writes redacted JSONL approval and execution events. Raw arguments, credentials and approval tokens are not written.
- `src/tools/system_tools.py` implements workspace reads/writes, patches, Git and subprocess execution.
- `src/conversation_runtime.py` owns the execution loop, tool feedback, streaming events, round limits and timeouts. The terminal and browser use the same runtime.

The browser displays pending approval state but does not approve privileged operations. The backend terminal must retain interactive stdin when privileged browser tool calls are expected.

## Execution environment decision

The user explicitly abandoned hardened isolation work. Debian PRoot-Distro is used as a compatibility and execution environment, **not as a security sandbox**.

Commands run with the permissions of the backend process. The project does not claim independent kernel identities, namespace isolation, cgroup limits, filesystem confinement or network isolation. Do not resume Bubblewrap, namespace, cgroup or capability-probe work unless explicitly requested.

Local approval remains valuable even without a sandbox: it gives the user a chance to inspect the exact operation before it runs. It is a consent control, not hostile-code containment.

## Tool policy

| Tool category | Behaviour |
|---|---|
| Read-only workspace inspection | Runs without an approval prompt |
| File writes and patches | Local approval; bounded diff preview; atomic replacement |
| Git mutations | Local approval |
| Shell commands | Local approval; bounded timeout/output; process-group cleanup |
| Unknown tools | Denied |
| URL fetching | Disabled until DNS pinning and redirect validation are implemented |
| Direct browser tool API | Disabled by default; when enabled, only read_file and list_dir |

Python writes and patches compile candidate source before replacement. Invalid syntax leaves the original file unchanged. File patch targets are size-bounded. Shell child environments exclude Gemini cookies and dashboard API keys.

## Audit behaviour

The audit log defaults to `~/.ww/audit/audit.jsonl` (overridable with `WW_AUDIT_LOG`). It records canonical tool names, keyed fingerprints, timestamps, decisions and outcomes without raw arguments or credentials. The log is bounded and uses restrictive file permissions. If an approval audit event cannot be durably recorded, the privileged operation is denied.

Archive the log before it reaches its cap with:

```bash
python -m src.tools.audit archive
```

Export a redacted copy to a new file in a private directory with:

```bash
python -m src.tools.audit export /path/to/private/audit-copy.jsonl
```

Execution-result audit failures are reported but cannot undo an operation that has already completed.

## Process lifecycle

The shared process runner:

- Starts POSIX subprocesses in their own process group.
- Bounds stdout/stderr capture and total execution time.
- Escalates from SIGTERM to SIGKILL when the process or descendants do not stop.
- Handles the edge case where a process closes stdout/stderr but continues running.
- Terminates descendants and reaps the parent on timeout or cancellation.

These are reliability controls. They do not make an approved command safe or isolated.

## Delivery status

- **2A, policy and approval primitives:** implemented; approval ledger primitives remain available but are not a remote approval API.
- **2B, local approval UX:** implemented in the shared runtime, including exact argument previews and bounded file diffs. Termux terminal interaction still needs device verification.
- **2C, isolation backend:** abandoned by explicit user decision. Historical evaluation notes are marked as such.
- **2D, audit and process recovery:** implemented and covered by unit tests; device-side verification remains outstanding.
- **2E, remote approval API:** not planned. The approval surface remains local terminal input unless the user requests a different trust model.

## Acceptance criteria

- Unknown tools fail closed.
- Invalid arguments are rejected before approval.
- Privileged model-generated tools require an explicit local decision.
- Direct browser tool execution remains read-only.
- File writes are atomic and invalid Python is rejected before replacement.
- Subprocess output and duration are bounded, and timed-out process groups are cleaned up.
- No claim is made that PRoot is a security sandbox.
- The complete Gemini → tool → approval → PRoot subprocess → feedback → Gemini cycle is verified on the actual Android device before declaring device readiness.
