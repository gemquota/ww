# AGENTS.md

## Project Overview
WW (Gemini Multi-Agent Bridge) is a Python-based CLI harness that provides an agentic coding loop powered by Google Gemini Web API. It implements a 3-tier agent hierarchy (Communicator → Overseer → Specialists) with tool execution, workspace sandboxing, SQLite-persisted memory, and context management.

## Architecture
- **3-Tier Agency**: Communicator (UI/Entry) → Overseer (Technical Lead) → Specialized Agents (Execution)
- **Model**: Gemini Web API only (via `gemini-webapi` library)
- **Memory**: SQLite-backed session persistence with 3-tier context (Hot → Facts → Summary) + Causal Graph (PCG)
- **Context**: Smart workspace ingestion with .gitignore awareness, token counting, and auto-compaction
- **Permissions**: Granular approval system for shell commands and file writes
- **Checkpoints**: Automatic git-based state snapshots with /undo support
- **Recovery**: AutoHealer escalates failures to Gemini for diagnosis/fix strategy
- **Tools**: Pydantic-schematized ToolRegistry with DAG dependency resolution
- **Benchmarks**: Structured task evaluation with execution traces

## Directory Structure
```
ww/
├── gemini_bridge.py      # Main orchestrator entry point (thin wrapper)
├── AGENTS.md             # Project instructions for AI agents
├── config.yaml           # Runtime configuration
├── requirements.txt      # Python dependencies
├── src/                  # Source package
│   ├── gemini_bridge.py  #   Main orchestrator (TUI, agent loop, tool dispatch)
│   ├── config.py         #   Pydantic-settings config loader
│   ├── context_manager.py#   ConversationHistory + RepoMapper + TokenCounter
│   ├── smart_context.py  #   Git-aware workspace context (gitignore, repo map)
│   ├── permissions.py    #   Sandbox + approval policy system
│   ├── diff_engine.py    #   Fuzzy SEARCH/REPLACE editing with colorized diffs
│   ├── checkpoint.py     #   Git checkpoint undo system
│   ├── agents_loader.py  #   Hierarchical AGENTS.md loader
│   ├── telemetry.py      #   Session logging (SQLite + JSONL)
│   ├── profiler.py       #   cProfile hot-path benchmarking
│   ├── debug_init.py     #   GeminiClient initialization tester
│   ├── core/             #   Ported from 2b:
│   │   ├── schemas.py    #     ToolCall Pydantic model
│   │   ├── memory.py     #     MemoryManager + SQLite + PCG
│   │   ├── healing.py    #     AutoHealer (Gemini diagnosis)
│   │   ├── benchmarker.py#     BenchmarkHarness with traces
│   │   └── judge.py      #     BenchmarkJudge (Gemini evaluation)
│   ├── tools/            #   Ported from 2b:
│   │   ├── registry.py   #     ToolRegistry with DAG
│   │   └── system_tools.py#    10 tool implementations + schemas
│   ├── utils/            #   Ported from 2b:
│   │   ├── web_client.py #     WebGeminiClient abstraction
│   │   └── validation.py #     Tool call extraction
│   ├── dashboard/        #   FastAPI web dashboard
│   │   └── app.py        #     REST API (health, chat, sessions, stats)
│   ├── plugins/          #   Plugin system
│   │   └── ww_plugin.py  #     PluginScanner + WWPlugin base class
│   └── gfx/              #   Mascot TUI
│       └── mascot_tui.py #     Terminal mascot with animated states
├── .tests/               # Test suite
│   ├── test_core.py      #   20 unit tests (schemas, memory, healing)
│   ├── test_tools.py     #   23 tests (registry, system tools, validation)
│   ├── test_integration.py#  26 tests (sandbox, permissions, checkpoint)
│   ├── test_set3.py      #   17 tests (DAG, new tools, plugins)
│   ├── test_quality_10dim.py# 46 quality dimension tests
│   ├── test_systemic_benchmarks.py # 38 systemic benchmarks
│   ├── test_trend_engine.py # ~10 trend engine tests
│   └── benchmarks/       #   Quality bench, regression gate, trend engine
├── deploy/               # Deployment
│   ├── Dockerfile        #   Container image
│   ├── docker-compose.yml#   Multi-service orchestration
│   └── .github/workflows/ci.yml  # CI pipeline
├── docs/                 # Documentation site (mkdocs)
├── agents/               # Agent markdown definitions (8 agents)
├── meta/                 # Audit, tasks, porting record, analysis
└── site/                 # Generated documentation site (static HTML)
```

## Setup Commands
- Install dependencies: `pip install -r requirements.txt`
- Set `SECURE_1PSID` and `SECURE_1PSIDTS` in `.env` (Gemini Web API credentials)
- Run the bridge: `python gemini_bridge.py`
- Run with verbose mode: `python gemini_bridge.py --verbose`
- Run syntax check: `python -m py_compile gemini_bridge.py`

## Code Style
- Python 3.10+ with asyncio patterns
- Use type hints for all function signatures
- Prefer `pathlib.Path` over `os.path` for file operations
- Use structured tool blocks (`tool:xxx`) for all system interaction
- Prefer surgical edits via `tool:replace` over full file rewrites

## Testing Instructions
- Syntax check: `python -m py_compile *.py core/*.py tools/*.py utils/*.py`
- Run benchmark tests: `python benchmarks/runner.py --suite benchmarks/golden_tasks.json`
- Verify sandboxing: attempt to read `/etc/passwd` (should be blocked)
- Verify memory: check `.ww/sessions/sessions.db` exists and has data

## Security Considerations
- NEVER read `.env` files or expose credentials
- All file operations are sandboxed to WORKSPACE_ROOT
- Shell commands require approval for unknown/dangerous operations
- Path traversal attacks are blocked by the Sandbox class
