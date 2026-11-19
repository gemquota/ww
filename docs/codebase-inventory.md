# WW codebase inventory and project assessment

**Snapshot:** 2026-11-20  
**Branch reviewed:** `integration/unified-runtime`  
**Main baseline:** `0043cb1516e2d4299e1804e4595e100917ad67d2`

This inventory classifies the repository rather than pretending every historical file is part of the supported application.

## Repository footprint

| Measure | Count |
|---|---:|
| Git tree entries | 441 |
| Files | 398 |
| Python files | 154 |
| Markdown files | 152 |
| HTML files | 8 |
| Test files | 21 |
| Documentation files under docs/ | 120 |

Top-level distribution:

| Area | Files | Assessment |
|---|---:|---|
| `src/` | 106 | Mixed: supported runtime plus legacy and experimental packages |
| `docs/` | 120 | Current docs plus historical V6/V7 proposals |
| `.old/` | 91 | Archived code snapshot; not active |
| `tests/` | 21 | Maintained unittest suite |
| `.github/` | 13 | Three active workflows plus repository metadata |
| `agents/` | 8 | Legacy agent prompts/definitions |
| `demo/` | 6 | Demonstrations and experiments |
| `deploy/` | 3 | Optional Dockerfile, compose file and instructions |
| `scripts/` | 3 | Current acceptance harness and package initializer |
| `chaos/`, `config/`, `mascot/` | 7 combined | Experimental/configuration/assets |

The repository is larger than the supported runtime. File counts include archived, historical and experimental material.

## Supported application path

The supported application has two frontends and one runtime:

```text
Terminal CLI ───────┐
                    ├── WWClient ── ConversationRuntime
GitHub Pages UI ────┘                    │
                                  Tool protocol
                                  Schema validation
                                  Local approval
                                  Tool registry
                                  Workspace/process tools
                                  Output feedback to Gemini
```

| Responsibility | Supported module |
|---|---|
| Terminal entry point | `gemini_bridge.py` |
| Gemini transport and conversation state | `src/ww_client.py` |
| Cookie loading | `src/cookie_loader.py` |
| Shared conversation/tool runtime | `src/conversation_runtime.py` |
| Tool fence parser and streaming filter | `src/tool_protocol.py` |
| Terminal prompting/history | `src/prompting.py` |
| Workspace context export | `src/project_context.py` |
| Local preferences and chat folders | `src/ww_settings.py` |
| Tool schemas | `src/tools/args.py` |
| Tool registration and validation | `src/tools/registry.py` |
| Workspace and subprocess operations | `src/tools/system_tools.py` |
| Workspace root resolution | `src/tools/workspace.py` |
| Risk policy and approval | `src/tools/tool_policy.py`, `src/tools/local_approval.py` |
| Audit log | `src/tools/audit.py` |
| Browser API and SSE | `src/dashboard/app.py` |
| Browser session lifecycle | `src/dashboard/session_store.py` |
| API auth, rate limiting and proxy handling | `src/dashboard/routes_auth.py` |
| Workspace-local database paths | `src/dashboard/db.py` |
| Static browser workspace | `src/dashboard/chat.html` |

The root `index.html` and `gh-pages` root `index.html` are synchronized with `src/dashboard/chat.html`. The Pages workflow deploys that same file. There is no longer a separate progress-dashboard deployment.

## Legacy and experimental source

These areas are retained as migration material or historical experiments. They are not supported entry points and must not be treated as proof that a feature is integrated.

| Area | Contents | Disposition |
|---|---|---|
| `src/gemini_bridge.py` | Older agent orchestration, memory and executor path | Entry point retired; unresolved names remain |
| `src/tool_executor.py` | Older DAG/tool executor | Deprecated; do not add new tools here |
| `src/context.py`, `src/tui.py`, `src/commands.py`, `src/tutorial.py`, `src/ui_adapter.py` | Previous UI/context and command framework | Legacy; silent approval adapter now denies by default |
| `src/core/` | Earlier core/agent framework | Historical implementation |
| `src/v7/` | V7 refactor/agent modules | Historical implementation |
| `src/bridge/` | Event bus, capability registry and related architecture experiments | Experimental; not used by supported runtime |
| `src/plugins/` | Plugin framework | Legacy/experimental |
| `src/demo/`, top-level `demo/`, `chaos/` | Demos and experiments | Not production runtime |
| top-level `agents/` | Agent definitions/prompts | Legacy |
| `.old/2b/` | Archived snapshot | Preserve for reference; do not import |
| `gen_explorer.py`, `docs/architecture-explorer.html` | Hard-coded V5 architecture visualization | Explicitly marked historical |
| `src/config.py`, `config.yaml` | Earlier YAML/agent configuration | Legacy settings, not the supported runtime's source of truth |

The old `src/gemini_bridge.py` and `src/tool_executor.py` have unresolved references. Their existence is not evidence of a working autonomous agent system. The supported terminal and browser clients do not depend on them.

## Branch and integration assessment

Feature branches were compared against the main baseline. The integration work selectively adopts useful terminal, session, approval, dashboard and process-management changes. It does not wholesale merge the broad `refactor/module-merging` branch or resurrect the old agent executor.

See [branch integration review](branch-integration-review.md) for branch-by-branch disposition and rationale.

## Dependencies

- `requirements.txt`: supported terminal/core runtime.
- `requirements-dashboard.txt`: core plus FastAPI/Uvicorn.
- `requirements-optional.txt`: legacy/experimental dependencies only.
- `docs-requirements.txt`: documentation tooling.
- `constraints.txt` was removed because it was not a lock file and duplicated stale lower bounds.
- `devcontainer.json` now targets Python 3.11 and installs dashboard dependencies.
- `pytest.ini` now points at `tests/`; unittest remains the canonical runner.
- `mypy.ini` targets Python 3.11.

## CI and deployment

Only three workflows remain active:

1. `.github/workflows/ci.yml`: compile checks, full unittest suite, transport contract and local API/process acceptance.
2. `.github/workflows/code-quality.yml`: Ruff and compile checks for maintained runtime modules.
3. `.github/workflows/pages.yml`: GitHub Pages frontend deployment.

Removed stale or conflicting infrastructure:

- The duplicate `tests.yml` and conditional test workflow.
- The competing `deploy-progress.yml` workflow.
- The inert `deploy/.github/workflows/ci.yml` nested workflow.
- The broken Terraform deployment path.
- The old progress dashboard and its duplicate root deployment artifact.
- The abandoned isolation capability probe and its tests.

The optional Docker setup was corrected: dashboard is the default command, compose has one local-loopback port mapping, healthcheck uses the public metadata route, and `.dockerignore` excludes cookies, `.env` and local state. Docker has not yet been built or run in CI.

## Supportive assessment

The project has substantial useful engineering already:

- A stateful Gemini Web Chat transport with resume and streaming.
- Cookie-file authentication and optional timestamp cookie handling.
- Conversation selection and local preferences.
- Workspace-aware context export.
- Markdown and elicitation rendering.
- Artifact and Android Canvas/WebView support.
- Explicit tool protocol, schema validation and central dispatch.
- Local approval, bounded diff previews and audit records.
- Bounded subprocess output, timeout and descendant cleanup.
- API-key protected local browser backend, CORS controls and bounded browser sessions.

The integration work preserves these strengths and gives them one execution path.

## Adversarial assessment

1. **The old autonomous bridge was not integrated.** It had its own ToolExecutor and unresolved references. It is now retired as an entry point.
2. **Some advertised tools were not usable.** The default read tool imported a nonexistent module; this is replaced by a bounded workspace reader.
3. **Tool schema ownership was inconsistent.** Schemas were moved to `args.py`; package exports and legacy imports needed repair.
4. **Invalid Python could be written before syntax checking.** Candidate source is now compiled before atomic replacement.
5. **Subprocess cleanup had a hanging edge case.** A child that closed pipes and ignored SIGTERM could keep the timeout path waiting; escalation is now bounded and regression-tested.
6. **A legacy silent UI adapter auto-approved everything.** It now denies by default.
7. **Dashboard database paths could ignore WW_WORKSPACE.** They now resolve it at call time.
8. **The old Pages workflow could overwrite the actual frontend.** It and the obsolete progress page were removed.
9. **The old Docker setup could not start the dashboard correctly.** It had a CLI ENTRYPOINT, conflicting ports, a protected healthcheck and no secret exclusions; the configuration was corrected but remains unverified.
10. **The repository's own instructions were stale.** AGENTS.md, CONTRIBUTING.md, pytest.ini, mypy.ini and the docs index now point to current modules and tests.

## Remaining verification gaps

- A real authenticated Gemini request and conversation resume.
- The complete Gemini → tool → local approval → PRoot subprocess → output feedback → Gemini cycle on the user's Android device.
- Actual Pages deployment and browser connection from Android.
- Browser parity for terminal-only media/artifact slash commands and multimodal attachments.
- Docker image build and runtime.
- Migration or retirement of advanced legacy agent/memory functionality.

The consolidated device run is `python -m scripts.termux_acceptance`. It runs the unit suite, workspace and process checks, and a local API smoke test using placeholder credentials. It does not claim live Gemini verification.

## Source of truth

For current behavior, prefer in this order:

1. Supported source and tests.
2. Current ADRs 006–010 in [the ADR index](adr/INDEX.md).
3. [Architecture review](architecture-review.md).
4. [Current API and tool docs](api/).
5. Root README.

Treat V6/V7 documentation, ADRs 001–005, the architecture explorer and archived code as historical context only.
