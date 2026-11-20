# Contributing to WW

Thanks for helping improve WW. The supported product is the Gemini Web Chat terminal client plus its local browser backend. Keep both clients on the shared ConversationRuntime.

## Development environment

Requirements: Python 3.11 or newer.

```bash
git clone https://github.com/gemquota/ww.git
cd ww
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dashboard.txt
```

For terminal-only work, `requirements.txt` is sufficient. Do not install `requirements-optional.txt` unless working specifically on a legacy/experimental subsystem.

Authentication is local. Use a Netscape-format `cookies.txt` containing the Google `__Secure-1PSID` cookie, or set `SECURE_1PSID` in your environment or gitignored `.env`. Never commit cookies, API keys, tokens, or generated workspace state.

## Supported entry points

Terminal:

```bash
python gemini_bridge.py
```

Local browser backend:

```bash
export WW_DASHBOARD_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export WW_WORKSPACE="$HOME/path/to/workspace"
uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8080
```

The static frontend is `src/dashboard/chat.html` and is deployed through the Pages workflow. Keep API credentials out of the frontend.

## Tests and quality checks

Run the maintained test suite:

```bash
python -m unittest discover -s tests -v
```

Run the consolidated acceptance harness (unit suite plus local API, CORS, workspace and subprocess checks):

```bash
python -m scripts.termux_acceptance
```

Compile all maintained Python source:

```bash
python -m compileall -q src scripts tests gemini_bridge.py ww_dev.py
python -m scripts.check_frontend_js  # requires Node.js
```

Ruff is used in CI for the maintained runtime modules. The CI workflow is authoritative; do not report a test as passing unless the command or CI result was observed.

The acceptance harness uses placeholder credentials and does not make a live Gemini request. Android Termux/PRoot device verification is a separate acceptance step documented in `docs/architecture-review.md`.

## Architecture expectations

- Use `src/ww_client.py` for Gemini Web Chat transport.
- Use `src/conversation_runtime.py` for chat, tool dispatch, approval, feedback and streaming.
- Register tools through `src/tools/registry.py` with schemas from `src/tools/args.py`.
- Use the same runtime from terminal and browser clients. Do not create a second executor or Gemini client for a new interface.
- Keep local approval for privileged writes, patches, Git mutations and shell commands.
- PRoot is an execution environment, not a hardened security sandbox. Do not add isolation machinery unless specifically requested.
- URL fetching remains disabled until its DNS/redirect protections are implemented.
- Keep local APIs loopback-bound by default and configure explicit CORS origins.

The old `src/gemini_bridge.py` entry point and the `src/tool_executor.py` stack are retired legacy migration source. Do not add new features there. If a legacy capability is valuable, migrate it into the shared runtime with tests.

## Pull requests

1. Branch from the latest `main`.
2. Check whether the feature already exists in main or another branch.
3. Make focused changes and add regression tests.
4. Run the tests and acceptance harness relevant to the change.
5. Update README or architecture documentation when behavior or setup changes.
6. Open a PR with a clear summary, test evidence, and any device-verification limits.

Prefer squash merges for feature PRs. Do not merge while required checks are failing or pending. Report genuine blockers rather than marking incomplete work as finished.
