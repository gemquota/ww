# WW architecture and adversarial review

**Review date:** 2026-11-20  
**Implementation branch:** integration/unified-runtime  
**Main baseline at review start:** 0043cb1516e2d4299e1804e4595e100917ad67d2

This review covers the terminal client, Gemini transport, tool execution, local approval, subprocess lifecycle, browser API, GitHub Pages frontend, branch history, dependencies, CI and the Android PRoot deployment model. The broader repository inventory, including historical and experimental modules, is recorded in [codebase-inventory.md](codebase-inventory.md).

## Executive assessment

WW has useful, well-developed pieces: a stateful Gemini Web Chat transport, cookie-file authentication, conversation selection, project-context export, Markdown rendering, generated-artifact handling, an Android Canvas WebView, approval policy, audit logging, bounded browser sessions, and process-group cleanup.

The central architectural defect was that these pieces did not form one application. The root terminal used WWClient without the tool executor; the browser used a separate WebGeminiClient; and the older agent bridge had its own ToolExecutor and registry. A merged feature set was being mistaken for an integrated runtime.

The integration branch now connects the default terminal and browser paths through ConversationRuntime and WWClient. It also replaces the old Pages progress dashboard with a proper browser workspace. This is a substantial correction, but it is not yet proof of a complete device-ready product. The older agent bridge remains a separate legacy path, and live Termux verification is still outstanding.

## Supportive review: existing strengths

- **Transport boundary:** WWClient owns one Gemini Web Chat session and provides connect, resume, send, streaming, model/Gem management and close operations.
- **Authentication:** cookie extraction is isolated in cookie_loader.py, validates Google-domain cookie entries, and treats SECURE_1PSIDTS as optional.
- **Conversation UX:** the terminal has startup chat selection, local folders, model/Gem preferences and multiline input.
- **Project awareness:** project_context.py inventories a workspace and bounds embedded content rather than blindly uploading every file.
- **Rendering and media:** Markdown/elicitation rendering and generated artifact handling preserve structured Gemini output.
- **Android integration:** canvas_browser.py uses a native Activity/WebView rather than pretending that a browser launch is an embedded workspace.
- **Approval and audit:** the Phase 2 work added central tool policy, local approval, bounded grants, diff previews, audit records and recovery tests.
- **Process lifecycle:** subprocess execution uses process groups, bounded pipe capture, timeout handling and descendant cleanup, including stubborn processes that close their pipes.
- **Dashboard foundations:** API-key validation, CORS restrictions, rate limiting, bounded sessions and per-session serialization are already present.

These are worth preserving. The problem was integration and inconsistent ownership, not a lack of useful engineering.

## Technical findings and changes

| Finding | Consequence | Integration response |
|---|---|---|
| Root terminal bypassed ToolExecutor | Model tool requests were not executed by the application users actually launched | Root CLI now uses ConversationRuntime. |
| Browser created WebGeminiClient sessions | Different authentication, session and transport semantics | Browser sessions now wrap WWClient and ConversationRuntime. |
| Browser ignored the shared cookie-file loader | A documented cookies.txt setup could work in the terminal but fail in the browser | Browser client loads WW_COOKIE_FILE and accepts optional SECURE_1PSIDTS. |
| Browser tool endpoint created a throwaway read-only registry | Chat and direct tools did not share dispatch or policy | Direct read-only calls now route through the shared runtime; privileged model tools use local approval. |
| ToolRegistry did not validate registered schemas | Malformed arguments could reach handlers | Central Pydantic validation now occurs before approval and execution. |
| read_file imported a missing src.smart_context module | The default read tool failed at runtime despite the registry and tests existing | Replaced it with a bounded UTF-8 workspace reader with byte, line and binary limits. |
| Tool package exports still imported schemas from system_tools | Importing src.tools failed after schemas were separated | Tool package now imports schemas from args.py and functions from system_tools.py. |
| src package exposed stale smart_context lazy exports | Public imports could fail even though the replacement project-context module existed | Removed stale exports and added lazy subpackage resolution for tools, dashboard and cookie_loader. |
| Python write/patch validation happened after modifying the file | A syntax error could leave a broken file in the workspace | Compile candidate source before atomic replacement; reject invalid edits without changing the original. |
| Process cleanup could wait indefinitely after a process closed pipes but ignored SIGTERM | Timeout cleanup could hang even though output capture had finished | Add a bounded process.wait phase and escalate to SIGKILL; add a regression test. |
| SilentUIAdapter approved every privileged action without a user | A legacy non-interactive path could silently approve operations | SilentUIAdapter now denies by default and has a regression test. |
| Dashboard database paths consulted legacy YAML settings | WW_WORKSPACE could be ignored when config.yaml supplied a workspace | Database paths now resolve WW_WORKSPACE at call time. |
| Project instructions, pytest config and contributor guide pointed at retired paths | Contributors and coding agents could follow nonexistent modules and test directories | AGENTS.md, CONTRIBUTING.md, pytest.ini, mypy.ini and the docs index now describe the maintained runtime. |
| Docker command, port and healthcheck configuration were inconsistent | Dashboard container could not start correctly and healthchecks required an API key | Dockerfile and compose were consolidated; healthcheck uses the public metadata route, host port binds loopback, and .dockerignore excludes secrets. |
| Synchronous tool handlers ran on the event loop | File operations could stall streaming and concurrent requests | Synchronous handlers now run in worker threads. |
| Workspace writes replaced files directly | Interrupted writes could leave partial files | write_file and file_patch use same-directory atomic replacement. |
| Python syntax validation ran after the write | A malformed edit could already have replaced the valid file | Candidate Python source is compiled before atomic replacement; invalid edits leave the original unchanged. |
| Git command parsing treated a whole command string as one argument | Commands such as git status --short could fail | Git subcommands and arguments are parsed with shlex and executed without a shell. |
| Shell children inherited Gemini and dashboard credentials | An approved shell command could inspect application credentials through its environment | Known Gemini and WW dashboard credential variables are removed from shell child environments. |
| URL fetching had incomplete SSRF checks | IPv6, DNS failures, rebinding and redirects were not robustly constrained | URL fetching is disabled until DNS pinning and redirect validation can be implemented. |
| Two CI workflows ran overlapping unit suites | Duplicate CI work obscured the canonical test path | The duplicate workflow was removed; core CI now compiles, runs the full unittest suite and starts the local API/process acceptance harness. |

## Adversarial review

### Input and tool protocol

- Only explicit top-level tool fences are executable. Ordinary Markdown code fences are not dispatched.
- JSON tool arguments are supported; JSON is recommended for multiline content and values containing code fences.
- Registered Pydantic schemas validate and normalize arguments before a privileged approval request is shown.
- Unknown tools fail closed.
- The runtime has bounded tool-call rounds, bounded total tool calls, per-tool timeouts and capped feedback payloads.
- Tool output is treated as untrusted data in the follow-up prompt.
- Tool events carry invocation IDs so repeated calls to the same tool do not overwrite one another in the browser UI.

### Filesystem and writes

- Workspace paths are resolved against the configured workspace root.
- Sensitive paths are blocked from the read-only file tool.
- Privileged write and patch operations require local approval; the approval controller displays the target and a bounded diff.
- Writes use atomic replacement and preserve the existing file mode where possible.
- The system is not a filesystem sandbox. Approved shell commands can still access anything available to the backend process. This is intentional under the user's decision to stop pursuing isolation.

### Processes

- Shell and Git operations execute in the backend process environment. If the backend is launched inside Debian PRoot, those commands execute in that environment.
- Shell operations require local approval and use a bounded timeout.
- The process runner starts a process group on POSIX and terminates descendants on timeout or cancellation.
- Output capture is bounded. Large output is truncated before it is fed back to Gemini.
- The shell child environment no longer contains the primary Gemini cookies or WW dashboard API keys.
- This is not hostile-code containment. A user-approved command has the capabilities of the backend process.

### Browser and API

- The browser page is static and contains no Gemini cookies or server-side secrets.
- The dashboard API requires an API key and uses a configured CORS allowlist.
- The API server binds to 127.0.0.1 by default.
- The browser stores the API key in sessionStorage and conversation text in localStorage. The UI provides a local-history clear action.
- Model-generated privileged operations display an approval-waiting event in the browser and ask for the decision in the backend Termux terminal.
- The direct browser tool endpoint remains opt-in and read-only.
- The browser uses DOM text nodes for model output, creates links only for HTTP(S) URLs, and does not insert model output as HTML.

## Product and deployment assessment

### GitHub Pages

The previous gh-pages index was an obsolete progress dashboard. It has been replaced with the current browser workspace. A second deploy-progress workflow used peaceiris/actions-gh-pages with force_orphan and could overwrite the Pages branch, so it has been removed. The main branch root index.html and gh-pages root index.html now match src/dashboard/chat.html. The old progress-dashboard.html and its competing deployment workflow have been removed. The remaining Pages workflow copies the browser workspace to the deployment artifact.

The repository Pages source setting still needs to be checked after integration. For Actions deployment, Settings → Pages → Build and deployment must use GitHub Actions. The gh-pages branch now also has a root index.html fallback for branch-based Pages configuration.

### Local backend

The backend uses the same WWClient and ConversationRuntime as the terminal. It can load the same cookies.txt file, uses WW_WORKSPACE as its working directory, and executes commands in the environment where the server is running. The dashboard database paths now resolve WW_WORKSPACE at call time rather than consulting the legacy YAML settings.

The approval prompt uses the backend terminal's standard input. Therefore the backend must remain attached to a usable foreground Termux terminal when privileged browser tool calls are expected. A detached server with no interactive stdin cannot provide the same approval UX.

### Browser conversation persistence

The browser keeps a local conversation list and stores Gemini conversation IDs. Backend session objects are bounded and in-memory; if a session is evicted or the backend restarts, the frontend can request a resume using the stored Gemini conversation ID. Local browser history is not a cloud backup.

## Remaining risks and work

1. **Legacy bridge:** src/gemini_bridge.py still contains its own ToolExecutor, Gemini client path, memory and orchestration stack. Static lint exposed unresolved names in this legacy code. Its direct entry point now exits with a deprecation message; it is not a supported runtime. Decide which advanced subsystems should be migrated into the shared runtime and which should be retired.
2. **Live device verification:** the new runtime and browser path have deterministic fake-client tests, but no actual Gemini → tool → approval → subprocess → Gemini cycle has yet been verified on the user's Android device.
3. **PR CI:** the integration branch must pass GitHub Actions before merge. The expanded unit and acceptance tests are in CI; the final result must be observed, not assumed.
4. **Pages deployment:** the frontend artifact and branch fallback have been updated, but the deployed public URL must be checked after the Pages workflow or branch deployment runs.
5. **Foreground approval:** terminal approval is deliberate, but the browser should clearly explain that the backend needs an interactive terminal. A future browser-mediated approval workflow would need its own explicit trust model.
6. **SSE keepalives:** a long Gemini thinking interval may exceed some proxy idle timeouts. Add heartbeat comments if live tunnel testing shows this is necessary.
7. **Browser feature parity:** media/artifact slash commands and attachment upload/rendering remain terminal-only. The shared chat/tool loop is unified, but the browser is not yet a complete replacement for every terminal command.
8. **Docker:** the old image/compose configuration had a CLI entrypoint that prevented the dashboard command override, duplicate host port mappings, an authenticated healthcheck and no Docker build-context secret exclusions. The Dockerfile, compose service and .dockerignore have been corrected, but the image has not yet been built or run in CI. Set WW_UID/WW_GID to match the host workspace owner when using bind mounts.
9. **URL fetching:** disabled until redirect and DNS pinning are correct.
10. **Process cancellation:** cancelling an asyncio task cannot forcibly stop a synchronous function already running in a worker thread. Current synchronous handlers are bounded local operations; long-running work should remain subprocess-based.
11. **Legacy feature parity:** the old advanced bridge contains memory, specialist agents and orchestration features that have not yet been migrated to the shared runtime.

## Verification levels

| Level | Evidence | Status |
|---|---|---|
| Static source review | Repository files and branch comparisons | Completed for the integration scope |
| Unit tests | Existing tests plus shared-runtime, prompting and shell-environment tests | Authored; CI result pending |
| Deterministic integration | Fake Gemini client exercises tool call, approval, output feedback and streaming | Authored; CI result pending |
| Local API acceptance | Temporary workspace, Uvicorn startup, API key, runtime metadata, CORS, browser page and process cleanup | Authored; CI result pending |
| Linux process behaviour | Existing process-group cleanup tests | Present; CI result pending |
| Real Gemini session | Actual authenticated request and conversation resume | Not verified in this turn |
| Android Termux / Debian PRoot | Actual browser chat, local approval, shell execution and process cleanup | Not verified in this turn |
| Public Pages deployment | Live page and API connection from Android browser | Not verified in this turn |

## Consolidated device acceptance run

After CI passes and the branch is merged, the device acceptance run should cover one sequence rather than many isolated prompts:

1. Start the backend from the intended Debian PRoot workspace.
2. Open the GitHub Pages frontend and connect using the loopback API URL and dashboard key.
3. Confirm runtime and Gemini credential readiness.
4. Ask WW to inspect a file in the configured workspace.
5. Ask WW to create a temporary file; verify that the approval appears in Termux, approve it, and confirm the returned file contents.
6. Ask WW to run a harmless command such as pwd and python --version; confirm the output and exit status.
7. Deny one privileged operation and confirm the denial is fed back to Gemini without executing it.
8. Stop a bounded long-running command and confirm its process group is cleaned up.
9. Reload the browser, resume the same Gemini conversation, and verify the local transcript and conversation ID.
10. Repeat from the terminal CLI and confirm the same tool protocol and approval behaviour.

No device acceptance claim should be made until the actual output from this sequence is reviewed.
