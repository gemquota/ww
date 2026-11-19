# WW project instructions

## Product and supported runtime

WW is a Gemini Web Chat client with a local workspace runtime. The supported application has two clients and one execution architecture:

- **Terminal:** `python gemini_bridge.py`
- **Browser backend:** `uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8080`
- **Static browser client:** `src/dashboard/chat.html`, published by `.github/workflows/pages.yml`

Both clients use `src/ww_client.py` and `src/conversation_runtime.py`. Do not create a second Gemini client, tool registry, or execution loop for a new interface. Browser sessions wrap the same WWClient and ConversationRuntime used by the terminal.

The old `src/gemini_bridge.py` entry point is retired. `src/tool_executor.py`, `src/context.py`, `src/tui.py`, `src/commands.py`, `src/tutorial.py`, `src/ui_adapter.py`, `src/bridge`, `src/core`, `src/v7`, `src/plugins`, top-level `agents/`, `demo/` and `chaos/` are legacy/experimental migration source, not supported application entry points. The retired bridge contains unresolved references. Do not build new features on it without first migrating the required behavior into the shared runtime.

## Core architecture

- `gemini_bridge.py`: supported terminal entry point, startup conversation picker, prompt loop and slash commands.
- `src/ww_client.py`: stateful Gemini Web Chat transport, cookie authentication, conversation resume, streaming and media.
- `src/cookie_loader.py`: Netscape cookie extraction and environment precedence.
- `src/conversation_runtime.py`: shared conversation state, tool protocol, validation, approval, feedback loop and streaming events.
- `src/tool_protocol.py`: explicit tool-fence parsing and streaming fence filtering.
- `src/tools/args.py`: Pydantic argument schemas.
- `src/tools/registry.py`: shared registry and schema validation.
- `src/tools/system_tools.py`: workspace and subprocess operations.
- `src/tools/local_approval.py`, `tool_policy.py`, `audit.py`: local approvals, risk classification and audit records.
- `src/dashboard/app.py`: authenticated local API and SSE endpoints.
- `src/dashboard/session_store.py`: bounded browser session lifecycle.
- `src/project_context.py`: project inventory and context export. There is no supported `src.smart_context` module.
- `src/markdown_renderer.py`, `src/artifacts.py`, `src/canvas_browser.py`: terminal rendering and optional media/Android integration.
- `src/ww_settings.py`: local preferences and chat-folder metadata.

## Execution and permissions

- WW is designed to run in Termux or Debian PRoot-Distro on Android, as well as ordinary Python environments.
- PRoot is the execution/compatibility environment, **not a security sandbox**. Do not claim namespace, filesystem, network, UID or capability isolation. Commands run with the permissions of the backend process.
- The user has explicitly abandoned hardened isolation work. Do not resume Bubblewrap, namespace or cgroup investigations unless asked.
- Model-generated writes, patches, Git mutations and shell commands require the shared local approval controller. Read-only tools do not.
- Shell commands execute in the backend process environment. Do not pass Gemini cookies or WW dashboard API keys into child command environments.
- URL fetching is disabled until DNS pinning, redirect validation and SSRF handling are implemented.
- The browser API binds to loopback by default. Do not expose it publicly without an HTTPS private tunnel/VPN and a configured CORS origin. CORS is not authentication.
- The direct browser `/tools/execute` endpoint is opt-in and read-only. Model-generated privileged tools use the shared runtime and local terminal approval.
- Keep output, file reads, tool rounds, subprocess duration and process cleanup bounded. Atomic file replacement is preferred. Validate candidate Python source before writing it.

## Dependencies and configuration

- `requirements.txt`: supported terminal/core dependencies.
- `requirements-dashboard.txt`: core plus FastAPI/Uvicorn for the local browser backend.
- `requirements-optional.txt`: legacy/experimental modules only; do not add optional dependencies to the core path without a demonstrated need.
- `.env`, `cookies.txt`, API keys and generated state are local secrets/data and must never be committed.
- `WW_WORKSPACE` selects the workspace. `WW_COOKIE_FILE` selects the Netscape cookie export. `WW_DASHBOARD_API_KEY` protects the local API. `WW_CORS_ORIGINS` configures explicit frontend origins.
- The static Pages frontend contains no Gemini credentials. Browser API keys remain in tab sessionStorage; browser transcripts are localStorage data.
- The old YAML settings/agent hierarchy is legacy configuration. Do not assume it configures the supported runtime unless a current call site proves it.

## Tests and CI

The maintained tests live in `tests/` and use `unittest` (including `IsolatedAsyncioTestCase`). The canonical commands are:

```bash
python -m compileall -q src scripts tests gemini_bridge.py
python -m unittest discover -s tests -v
python -m scripts.termux_acceptance
```

The acceptance harness runs the unit suite, exercises workspace tools and process cleanup, starts the local API against a temporary workspace, and checks API authentication, runtime readiness, Pages CORS and static browser-page serving. It uses placeholder credentials and does not authenticate to Gemini.

CI is defined by:
- `.github/workflows/ci.yml`: compile, unit/integration tests, local API/process acceptance.
- `.github/workflows/code-quality.yml`: Ruff and compile checks.
- `.github/workflows/pages.yml`: deploy the browser frontend.

Do not refer contributors to `.tests/`, `.tel/tests/`, or a nonexistent Makefile. Do not claim live Gemini or Android device verification based solely on unit tests or GitHub Actions. The actual device acceptance sequence is documented in `docs/architecture-review.md`.

## Engineering rules

1. Inspect the current mainline and relevant feature branches before implementing overlapping functionality.
2. Prefer integrating existing modules over parallel implementations.
3. Preserve working behavior and add tests for regressions.
4. Keep the terminal and browser clients on the same runtime and policy path.
5. Use the narrowest dependency set that supports the active application.
6. Distinguish implemented code, unit-tested components, CI integration tests and real device verification in all status reports.
7. Update README and architecture docs when behavior changes. Treat legacy docs as untrusted until checked against current code.
8. Never claim a deployment, merge, test pass or device verification unless its result has been observed.
