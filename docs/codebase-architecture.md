# WW Bridge — Codebase Architecture Reference

> Generated: 2026-06-14
> After comprehensive modularization refactor (Phase 1-3)

## Overview

WW (Gemini Multi-Agent Bridge) is a Python CLI harness providing an agentic coding loop powered by Google Gemini Web API. It implements a multi-agent routing architecture (Communicator → Overseer → Specialists with cross-delegation, pipeline chains, and parallel fan-out) with tool execution, workspace sandboxing, SQLite-persisted memory, and context management.

**Total runtime source:** 30 files, ~5,000 lines
**Test suite:** 10 files, 197 tests, 100% pass rate

---

## Package Structure

```
src/                          # Runtime package root
├── __init__.py               # Public API facade (re-exports)
├── _constants.py             # Shared constants (BASE_IGNORE, CRITICAL_FILES, etc.)
├── gemini_bridge.py          # Main orchestrator (TUI + agent loop + dispatch)
├── tool_executor.py          # LLM tool block parser & dispatcher
├── context_manager.py        # 3 classes: TokenCounter, ConversationHistory, RepoMapper
├── smart_context.py          # Git-aware workspace context assembly
├── config.py                 # Pydantic-settings config (YAML + env vars)
├── permissions.py            # Sandbox boundaries + approval policies
├── diff_engine.py            # Fuzzy SEARCH/REPLACE with colorized diff
├── checkpoint.py             # Git-patch checkpoint system for /undo
├── agents_loader.py          # Hierarchical AGENTS.md loader
├── telemetry.py              # SQLite + JSONL session logging
├── file_watcher.py           # Polling file change detector
│
├── core/                     # Core subsystems
│   ├── schemas.py            # Pydantic models
│   ├── memory.py             # MemoryManager + SessionDatabase + PCG
│   ├── healing.py            # AutoHealer (Gemini diagnosis)
│   ├── benchmarker.py        # Benchmark harness + traces
│   └── judge.py              # Benchmark evaluation (Gemini)
│
├── tools/                    # Tool system
│   ├── registry.py           # ToolRegistry + DAG resolution
│   └── system_tools.py       # 11 tool implementations + Pydantic schemas
│
├── utils/                    # Shared utilities
│   ├── web_client.py         # Gemini Web API client
│   └── validation.py         # Tool call extraction from LLM output
│
├── dashboard/                # FastAPI web dashboard
│   └── app.py                # REST API endpoints
│
├── plugins/                  # Plugin system
│   └── ww_plugin.py          # PluginSpec + WWPlugin + PluginScanner
│
└── gfx/                      # Terminal mascot
    └── mascot_tui.py         # Animated mascot with state machine

.tel/                         # Runtime data (gitignored)
.tel/.tests/                  # Test suite (197 tests)
.tel/.tests/benchmarks/       # Benchmark harness
    ├── profiler.py           # cProfile hot-path benchmarking
    ├── quality_bench.py      # Quality dimension benchmarks
    ├── regression_gate.py    # Regression detection
    ├── runner.py             # Benchmark runner
    └── trend_engine.py       # Trend analysis engine
```

---

## Component Dependency Graph

```
gemini_bridge.py ──→ context_manager.py    (ConversationHistory, TokenCounter, RepoMapper)
                 ──→ smart_context.py       (workspace context assembly)
                 ──→ permissions.py         (Sandbox, PermissionManager)
                 ──→ diff_engine.py         (DiffEngine)
                 ──→ checkpoint.py          (CheckpointManager)
                 ──→ agents_loader.py       (load_all_instructions)
                 ──→ telemetry.py           (TelemetryManager)
                 ──→ tool_executor.py       (ToolExecutor)
                 ──→ core/memory.py         (MemoryManager)
                 ──→ core/healing.py        (AutoHealer)
                 ──→ core/schemas.py        (ToolCall)
                 ──→ tools/registry.py      (ToolRegistry)
                 ──→ tools/system_tools.py  (all tool implementations)
                 ──→ utils/web_client.py    (WebGeminiClient)
                 ──→ utils/validation.py    (extract_tool_call)
                 ──→ config.py              (get_settings)

tool_executor.py ──→ smart_context.py      (read_file_surgical, get_directory_context)
                 ──→ core/memory.py         (MemoryManager)
                 ──→ tools/registry.py      (ToolRegistry)
                 ──→ permissions.py         (PermissionManager, Sandbox)
                 ──→ diff_engine.py         (DiffEngine)
                 ──→ checkpoint.py          (CheckpointManager)
                 ──→ telemetry.py           (TelemetryManager)
                 ──→ context_manager.py     (ConversationHistory)

smart_context.py ──→ _constants.py          (BASE_IGNORE, CRITICAL_FILES, truncation limits)

dashboard/app.py ──→ utils/web_client.py    (WebGeminiClient)
                 ──→ tools/registry.py      (ToolRegistry)
                 ──→ tools/system_tools.py  (tool schemas)
                 ──→ telemetry.py           (TelemetryManager)
                 ──→ config.py              (get_settings)

core/healing.py  ──→ utils/web_client.py    (WebGeminiClient)
core/judge.py    ──→ utils/web_client.py    (WebGeminiClient)
utils/web_client.py ──→ config.py           (get_settings)
```

---

## Key Constants (single source of truth: `src/_constants.py`)

| Constant | Value | Used By |
|---|---|---|
| `BASE_IGNORE` | `{".git", "node_modules", "__pycache__", ...}` | smart_context, context_manager, file_watcher |
| `CRITICAL_FILES` | `{"AGENTS.md", "README.md", "requirements.txt", ...}` | smart_context, context_manager |
| `PARSEABLE_EXTENSIONS` | `{".py", ".js", ".ts", ".rs", ".go", ...}` | context_manager (RepoMapper) |
| `MAX_FILE_LINES_DEFAULT` | 150 | smart_context |
| `MAX_FILE_LINES_CRITICAL` | 100 | smart_context |
| `MAX_FILE_LINES_AGENTS` | 400 | agents_loader |
| `MAX_TREE_LINES` | 200 | smart_context |

---

## Configuration System

```
config.yaml ──→ Settings (Pydantic) ──→ WW_* env vars
                                   ──→ gemini.* (timeout, retries, rate limit)
                                   ──→ memory.* (max_tier_a, compress_threshold, max_checkpoint_count)
                                   ──→ dashboard.* (host, port)
                                   ──→ plugins.* (directory, auto_load)
                                   ──→ logging.* (level, format)
```

Config wired into runtime via:
- `CheckpointManager._prune_old_checkpoints()` reads `MemoryConfig.max_checkpoint_count`
- `WebGeminiClient._get_config_rate_limit()` reads rate limit from config
- `Settings.resolve_workspace()` used by tools for sandbox root

---

## Single Responsibility Audit

| Module | Responsibility | Status |
|---|---|---|
| `_constants.py` | Shared constants | ✅ Single purpose |
| `config.py` | Configuration loading | ✅ Single purpose |
| `permissions.py` | Sandbox + approval policy | ✅ Single purpose |
| `diff_engine.py` | Fuzzy SEARCH/REPLACE | ✅ Single purpose |
| `checkpoint.py` | Git checkpoint / undo | ✅ Single purpose |
| `agents_loader.py` | AGENTS.md discovery | ✅ Single purpose |
| `telemetry.py` | Session logging | ✅ Single purpose |
| `file_watcher.py` | File change detection | ✅ Single purpose |
| `smart_context.py` | Workspace context assembly | ✅ Single purpose |
| `context_manager.py` | 3 classes (token count, history, repo map) | ⚠️ OK (cohesive) |
| `gemini_bridge.py` | Orchestrator (TUI + loop + dispatch) | ⚠️ Sprawling (644 lines) |
| `tool_executor.py` | Tool parsing + dispatch | ✅ Simplified |
| `core/memory.py` | Memory + persistence + PCG | ⚠️ Too large (462 lines) |
| `core/healing.py` | Auto-healing via Gemini | ✅ Clean |
| `tools/system_tools.py` | 11 tool implementations | ⚠️ Could split schemas |
| `dashboard/app.py` | REST API | ⚠️ Could modularize routes |

---

## Duplication Eliminated

| Pattern | Before | After | Delta |
|---|---|---|---|
| `BASE_IGNORE` constant | 3 copies | 1 (`_constants.py`) | -67% |
| `CRITICAL_FILES` constant | 2 copies | 1 (`_constants.py`) | -50% |
| `is_safe_path()` method | 2 copies (ToolExecutor, Sandbox) | 1 (Sandbox only) | -50% |
| `_parse_fields_stream_friendly()` | Duplicate of `_parse_fields()` | Removed | -100% |
| `log_status()` body | Duplicate (gemini_bridge, tool_executor) | 1 (tool_executor only) | -50% |
| `compact_with_llm()` stub | Dead NotImplementedError | Removed | -100% |

---

## Dead Code Removed

| What | Where | Reason |
|---|---|---|
| `profiler.py` | src/ → .tests/benchmarks/ | Dev/CI tool, not runtime |
| `debug_init.py` | src/ → removed | Subsumed by `--verbose` flag |
| `lazy_import.py` | src/utils/ | Never imported by any module |
| Compact w/ LLM stub | context_manager.py | Raises NotImplementedError |
| Duplicate log_status body | gemini_bridge.py | Dead fallthrough |
| Unused parser variant | tool_executor.py | Never called in main flow |
| Root-level duplicates | `agents_loader.py`, `checkpoint.py`, etc. | Superseded by src/ |
| Duplicate gfx/ | `gfx/` (root) | `src/gfx/` is canonical |
| Audit files | `WORKSPACE_AUDIT.md`, `l2audit.md` | Static reports |

---

## Remaining Technical Debt (Future Work)

1. **`gemini_bridge.py` (644 lines)** — Extract TUI layer, command handlers, and session orchestration into separate modules
2. **`core/memory.py` (462 lines)** — Extract `SessionDatabase` and `MemoryGraph` (PCG) into own files; simplify cache invalidation
3. **`tools/system_tools.py` (306 lines)** — Extract argument schemas into `tools/schemas.py`; separate file/network/shell tools
4. **`dashboard/app.py` (303 lines)** — Modularize into route handlers with FastAPI dependency injection
5. **`TelemetryManager` connection** — Use persistent SQLite connection instead of open/close per call
6. **`FileWatcher` callback** — Wire a real callback so the watcher actually does something
