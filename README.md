# WW Bridge — The First Agentic Coding Tool for Google Gemini

[![CI](https://github.com/yourorg/ww/actions/workflows/ci.yml/badge.svg)](https://github.com/yourorg/ww/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-197%20passing-brightgreen.svg)](.tests/)

> **Run a multi-agent coding team on your machine, powered by Gemini.**
> No SaaS, no API key subscription — just a browser cookie and a terminal.
> WW Bridge is the only agentic coding tool that works with Google Gemini,
> runs entirely locally, and persists memory across sessions.

---

## Features

- **🤖 3-Tier Agent Hierarchy** — Communicator (entry), Overseer (planning), Specialists (execution)
- **🔧 11 Built-in Tools** — read, write, search, shell, git, patch, fetch, and more
- **🧠 Smart Context** — Git-aware workspace ingestion with `.gitignore` respect, token counting, and auto-compaction
- **🔒 Sandbox Security** — Path traversal prevention, approval policies (always/on-request/never)
- **💾 Persistent Memory** — 3-tier context (Hot → Facts → Summary) + Causal Graph (PCG) in SQLite
- **↩️ Undo Support** — Automatic git checkpoints before file writes; `/undo` to revert
- **🔌 Plugin System** — Extensible via Python plugins with lifecycle hooks
- **📊 Web Dashboard** — FastAPI dashboard for session history, telemetry, and health monitoring
- **📈 Benchmark Suite** — 197 tests with quality metrics across 10 dimensions
- **🐳 Docker Support** — Containerized deployment with docker-compose

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set credentials in .env
echo "SECURE_1PSID=your_value" >> .env
echo "SECURE_1PSIDTS=your_value" >> .env

# 3. Run interactive mode
python3 gemini_bridge.py

# 4. Try a query
# "list all Python files in the project"
```

```
                          ┌──────────────────────┐
                          │    COMMUNICATOR       │
                          │  (Entry / UI)         │
                          └──┬──┬──┬──┬──┬──┬────┘
                    ┌────────┘  │  │  │  │  │
                    │     ┌─────┘  │  │  │  │
                    ▼     ▼        ▼  ▼  ▼  ▼
              ┌────────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
              │OVERSEER│ │CODER│ │RECH│ │TEST│ │SEC │ │ARCH│
              │(Tech   │ │     │ │    │ │    │ │    │ │    │
              │ Lead)  │ │     │ │    │ │    │ │    │ │    │
              └────┬───┘ └────┘ └────┘ └────┘ └────┘ └────┘
         ┌─────────┼──────────┬──────────┬──────────┬──────┐
         ▼         ▼          ▼          ▼          ▼      ▼
    ┌────────┐ ┌────┐ ┌────────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
    │ CODER  │ │RECH│ │ TESTER │ │SEC │ │ARCH│ │... │ │... │
    └────┬───┘ └────┘ └────────┘ └────┘ └────┘ └────┘ └────┘
         │    ┌──────────────────────────────────────────┐
         └────┤ Specialist ↔ Specialist lateral edges   │
              │ (any agent can call any other agent)     │
              └──────────────────────────────────────────┘

Communication Patterns:
◆ Communicator → single pass-through lines to ALL agents (incl. Overseer)
◆ Overseer → pipelines specialists, chains I/O, collects+processes results
◆ Collect Pattern: Two+ agents → one agent → another → Overseer
◆ Chain Pattern: Coder → Tester → Security → Overseer
◆ Results flow upward (particles go out the top)
◆ Any specialist can delegate laterally to any other
```


    Delegation/reference flows down spines and across rows.
    Results flow back up (particles go out the top).
    Any agent can delegate to any neighbor — horizontally or vertically.
```

### Communication Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **Direct Delegation** | Communicator or Overseer calls any single specialist | `coder: implement this function` |
| **Parallel Fan-Out** | One agent delegates to multiple specialists independently | `researcher` + `architect` in parallel |
| **Pipeline Chain** | Output of one specialist feeds into another | `researcher → coder → tester` |
| **Collect + Process** | Gather results from multiple agents, process, then pass to another | `researcher + architect → process → coder` |
| **Specialist-to-Specialist** | A specialist delegates to another specialist mid-task | `coder delegates to security for review` |
| **Multi-Agent Feedback Loop** | Two agents feed into a third, whose output goes back to the orchestrator | `architect + security → coder → overseer` |

### Routing Rules

- **Communicator** delegates to the **Overseer** for complex tasks, or directly to a **Specialist** for simple, well-defined tasks
- **Overseer** decomposes tasks and can call any combination of specialists in any order
- **Specialists** operate independently but can delegate to each other for cross-cutting concerns
- All agent sessions persist independently, so each agent maintains context across multiple calls in a session

Each specialized agent has a dedicated `agents/<name>.md` file with protocol instructions,
available tools, and behavioral guidelines.

---

## Why WW Bridge?

| Capability | WW Bridge | Claude Code | Codex CLI | Aider |
|---|---|---|---|---|
| Works with **Gemini** | **Yes** | No | No | No |
| Runs **locally** | **Yes** | Yes | Yes | Yes |
| **Free** (Gemini tier) | **Yes** | $20/month | API costs | API costs |
| **3-tier memory** | **Yes** | Window only | Window only | No |
| **Agent hierarchy** | **3 tiers** | 1 | 2 | 1 |
| **Web dashboard** | **Yes** | No | No | No |
| **Plugin system** | **Yes** | No | No | Extensions |

## Project Structure

```
ww/
├── gemini_bridge.py        # CLI entry point (thin wrapper)
├── config.yaml             # Runtime configuration
├── requirements.txt        # Python dependencies
├── .env                    # Credentials (gitignored)
│
├── src/                    # Runtime package (28 files)
│   ├── gemini_bridge.py    # Orchestrator (TUI, agent loop, dispatch)
│   ├── tool_executor.py    # Tool block parser and dispatcher
│   ├── context_manager.py  # TokenCounter, ConversationHistory, RepoMapper
│   ├── smart_context.py    # Git-aware workspace context assembly
│   ├── config.py           # Pydantic-settings config loader
│   ├── permissions.py      # Sandbox + approval policies
│   ├── checkpoint.py       # Git checkpoint / undo system
│   ├── _constants.py       # Shared constants (BASE_IGNORE, etc.)
│   ├── telemetry.py        # Session logging (SQLite + JSONL)
│   ├── diff_engine.py      # Fuzzy SEARCH/REPLACE engine
│   ├── agents_loader.py    # Hierarchical AGENTS.md loader
│   ├── file_watcher.py     # File change detector
│   ├── core/               # Memory, schemas, healing, benchmarks
│   ├── tools/              # ToolRegistry + 11 tool implementations
│   ├── utils/              # WebGeminiClient, validation
│   ├── dashboard/          # FastAPI web dashboard
│   ├── plugins/            # Plugin system
│   └── gfx/                # Terminal mascot
│
├── agents/                 # Agent markdown definitions (8 files)
├── deploy/                 # Docker, docker-compose, CI workflow
├── docs/                   # Documentation (19 files, 1,326 lines)
├── .tests/                 # Test suite (197 tests, symlink → .tel/.tests/)
└── reports/                # Modularization audit reports
```

---

## Security

WW Bridge implements three security layers:

1. **Workspace Sandbox** — All file operations validated against `Sandbox.is_safe_path()`
2. **Approval Policies** — `always` / `on-request` / `never` for shell commands
3. **Protected Paths** — `.env`, `.git/`, `.ww/` are always blocked

See [Security Model](docs/security.md) for details.

---

## Test Suite

```bash
# Run all 197 tests
pytest .tests/ -v

# Run specific test file
pytest .tests/test_core.py -v

# Run benchmarks (requires API keys)
python .tel/.tests/benchmarks/runner.py --suite .tel/.tests/benchmarks/golden_tasks.json
```

Tests cover:
- Schema validation (ToolCall, Pydantic models)
- Memory operations (3-tier, PCG, SQLite)
- Tool registry and DAG resolution
- Sandbox path traversal prevention
- Permission policies and approval flows
- Context compaction and token counting
- Diff engine and checkpoint system
- Agent instruction loading
- Quality dimensions (10 metrics)

---

## Deployment

```bash
# Docker
docker compose -f deploy/docker-compose.yml up ww-bridge

# Docker with dashboard
docker compose -f deploy/docker-compose.yml up dashboard

# Production
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml up
```

See [Deployment Guide](docs/deployment.md) for production considerations.

---

## Python API

Use WW Bridge components programmatically from your own scripts:

```python
# Example 1: Single query via WebGeminiClient
from src.utils.web_client import WebGeminiClient

async def ask_gemini(query: str) -> str:
    client = WebGeminiClient()
    await client.init()
    return await client.ask(query)

# Example 2: Use built-in tools
from src.tools.system_tools import read_file, list_dir
from src.tools.system_tools import ReadFileArgs, ListDirArgs

files = list_dir(ListDirArgs(path="src/"))
content = read_file(ReadFileArgs(path="src/gemini_bridge.py"))

# Example 3: Custom tool registration
from src.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register("my_tool", my_handler, "My custom tool", MyArgs)
```

> **Requires**: Valid `SECURE_1PSID` and `SECURE_1PSIDTS` in `.env`. See `--auth`.

---

## Architecture Overview

> **Interactive visualization available** — Open
> [`docs/architecture-explorer.html`](docs/architecture-explorer.html) in a
> browser to explore all 34+ modules across 11 interactive graph views
> (venn diagrams, data pipelines, dependency hubs, agent hierarchy, and more).



```
┌──────────────────────────────────────────────────────────────────┐
│                        USER (Terminal)                            │
└──────────────────────┬───────────────────────────────────────────┘
                       │ prompt_toolkit TUI
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    gemini_bridge.py (Orchestrator)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Permis-  │ │ Diff     │ │ Check-   │ │ ConversationHistory  │ │
│  │ sions    │ │ Engine   │ │ point    │ │ + TokenCounter       │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Memory   │ │ WebGemini│ │ Auto-    │ │ smart_context        │ │
│  │ Manager  │ │ Client   │ │ Healer   │ │ + RepoMapper         │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │ Tool     │ │ Tool     │ │ agents_  │                        │
│  │ Registry │ │Executor  │ │ loader   │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
└──────────────────────────────────────────────────────────────────┘
                       │ Gemini Web API
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Google Gemini (Cloud)                           │
└──────────────────────────────────────────────────────────────────┘
```

---

## Contributing

1. Run the test suite: `pytest .tests/ -v`
2. Ensure all 197 tests pass before submitting changes
3. Follow existing code style (type hints, pathlib, async patterns)
4. Update documentation for new features
5. See [Development Guide](docs/development.md) for details

---

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with [gemini-webapi](https://pypi.org/project/gemini-webapi/)
- Inspired by [Claude Code](https://claude.ai) and [Codex CLI](https://github.com/openai/codex)
- Multi-agent routing patterns adapted from [SWE-agent](https://github.com/princeton-nlp/swe-agent)
