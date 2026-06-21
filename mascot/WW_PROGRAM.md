# WW Bridge — Program Architecture & Capabilities

---

## 1. What WW Is

WW is a terminal-based agentic coding harness powered by Google Gemini. It gives an LLM structured access to a filesystem — read, write, patch, shell, git — inside a permission-sandboxed workspace, coordinated through a 3-tier agent hierarchy.

```
User ──► Communicator ──► Overseer ──► Specialists
                                     │
                                     ├── read_file / write_file
                                     ├── shell_exec / git
                                     ├── code_search / doc_search
                                     └── url_fetch / file_patch
```

The bridge does NOT run autonomously. Every tool call is either approved inline (permission profiles) or logged for audit. The user stays in the loop.

---

## 2. Feature Inventory

### 2.1 Core Agent Loop
- CLI entry point with argparse (`--script`, `--session`, `--demo`, `--health`, `--auth`)
- Gemini Web API interaction via `gemini-webapi` library
- Cookie-based (free tier) or API-key authentication
- Conversation history with token-aware context window management
- Auto-compaction when context approaches token limit

### 2.2 Tool System
- Pydantic-schematized tool definitions with DAG dependency resolution
- 11 tools: `read_file`, `write_file`, `file_patch`, `list_dir`, `shell_exec`, `git`, `doc_search`, `code_search`, `request_clarification`, `url_fetch`, `update_scratchpad`
- ToolRegistry with circular dependency detection and topological sort
- Async execution with `asyncio.gather()` for parallel-independent tools

### 2.3 Security & Permissions
- `PermissionManager` with 3 levels: allow-all, approval-required, deny
- Path traversal protection (`is_safe_path` blocks `/etc/passwd`, `.env`)
- Workspace sandboxing to `WORKSPACE_ROOT`
- Granular approval: shell commands, file writes, git operations

### 2.4 Context Management
- `ConversationHistory` — ring buffer with token counting
- `RepoMapper` — git-aware file listing with `.gitignore` respect
- `TokenCounter` — tiktoken-based token estimation
- `SmartContext` — workspace ingestion with truncation for large files/logs
- Context priming through identity + workspace messages

### 2.5 Persistence
- SQLite-backed telemetry (sessions, interactions, tool usage)
- SQLite-backed memory (conversation history, semantic graph)
- JSONL prompt logging for audit
- WAL journaling with auto-checkpoint

### 2.6 Checkpoint System
- Git-based automatic snapshots via `CheckpointManager`
- `/undo` restores previous checkpoint
- Rollback safety checks (won't undo past available history)
- Blast radius containment with try/except fallbacks

### 2.7 Diff Engine
- Fuzzy SEARCH/REPLACE matching (0.85 similarity threshold)
- Colorized unified diff output
- Side-by-side terminal rendering
- SearchReplaceValidator: detects ambiguous matches, validates Python syntax in REPLACE blocks

### 2.8 Multi-Agent Orchestration
- 3-tier hierarchy: Communicator → Overseer → Specialist
- Agent markdown definitions in `agents/*.md`
- `DecisionTracer` — tracks delegation decisions
- `CausalGraph` — persistent cognitive graph for decision lineage
- `EventBus` — pub/sub for cross-component communication

### 2.9 Dashboard API
- FastAPI REST server on port 8080
- API key authentication via `X-API-Key` header
- Rate limiting (100 req/min per IP)
- API versioning (`/api/v1/`)
- Endpoints: `/health`, `/chat`, `/sessions`, `/session/{id}`, `/stats`, `/stats/metering`, `/tools/execute`, `/memory/graph/{id}`

### 2.10 Deployment
- Multi-stage Dockerfile with non-root user
- Docker Compose for multi-service orchestration
- Terraform IaC (Docker provider)
- CI/CD via GitHub Actions (5 workflows)
- Devcontainer for reproducible dev environments

---

## 3. AI Evaluation Framework

### 3.1 Purpose
The eval framework (`src/core/evaluation.py`) provides structured measurement of agent output quality. It's designed for regression testing against prompt changes — NOT for production monitoring.

### 3.2 Components

| Component | File | Function |
|---|---|---|
| `EvalResult` | `evaluation.py` | Dataclass for single test result (pass/fail, score, duration) |
| `EvaluationSuite` | `evaluation.py` | Test runner aggregating results, producing JSON reports |
| `analyze_prompt_quality()` | `evaluation.py` | Heuristic prompt scoring (has examples? constraints? context?) |
| `check_tool_safety()` | `evaluation.py` | Scans tool invocations for dangerous patterns (rm -rf, /etc writes) |
| `MetricsAggregator` | `decomposition.py` | Per-category metric collection (mean/min/max per category) |
| `SensitivityAnalyzer` | `utils/sensitivity.py` | Perturbation testing — how does output change with small input changes? |
| `RefusalTester` | `utils/sensitivity.py` | Tests that the agent properly refuses dangerous/out-of-scope requests |
| `PromptQualityTest` | `test_evaluation_quality.py` | Automated evaluation test cases |

### 3.3 Is It Useful?

**Yes, for specific scenarios:**
- Before/after prompt template changes: run suite, verify no regression
- During critique implementation: validate that new modules don't break eval
- For benchmarking tool call quality: tracks precision of SEARCH/REPLACE edits

**No, it's not monitoring:**
- It doesn't run in production
- It requires labeled test data to be meaningful
- The heuristic scoring (`analyze_prompt_quality`) is basic — length + keyword checks

### 3.4 Real Usage

```
EvaluationSuite("prompt_v2")
  ├── run_test("code_quality", ..., check_tool_safety)
  ├── run_test("prompt_clarity", ..., analyze_prompt_quality)
  ├── record_metrics("code_gen", 0.85)
  ├── record_metrics("shell_safety", 1.0)
  └── save_report("eval_report.json")
```

The JSON report feeds into CI for regression gates. If a prompt change drops the score below threshold, CI fails.

---

## 4. Bridge Orchestration

### 4.1 What It Is
A set of modules in `src/bridge/` that coordinate multi-agent activity. They track decisions, propagate events, manage capabilities, and inject faults for testing.

### 4.2 Module Breakdown

| Module | LOC | Actual Utility |
|---|---|---|
| `causal_graph.py` | 254 | Persistent DAG of agent decisions. Links each action to its parent request. Provides `/memory/graph/{id}` API data. **Used.** |
| `event_bus.py` | 95 | Pub/sub bus for inter-component events. Currently 3 subscribers (telemetry, mascot, causal graph). **Light usage.** |
| `decision_tracer.py` | 122 | Tracks delegation chains: who delegated to whom and why. Queried for audit. **Used for debugging.** |
| `capability_registry.py` | 76 | Registry of agent capabilities per tier. Maps agent name → supported tools. **Used at startup.** |
| `profile_manifest.py` | 74 | Agent profile manifests (template versions, plugin set, memory policies). **Speculative — minimal current use.** |
| `fault_injector.py` | 67 | Chaos testing: simulates API outages, disk full, SQLite locks. **Used only in chaos engineering tests.** |

### 4.3 Data Flow

```
User Query
    │
    ▼
Communicator (gemini_bridge.py)
    │  sanitizes input, adds context
    ▼
Gemini API
    │  returns response with tool:xxx calls
    ▼
ToolExecutor (tool_executor.py)
    │  parses tool: blocks, resolves DAG
    ├──► ToolRegistry.execute()
    │       │
    │       ▼
    │   PermissionManager.check()  ──► denied → CONFUSED
    │       │ approved
    │       ▼
    │   Tool runs (read_file, shell, etc.)
    │       │
    │       ▼
    │   EventBus.emit("tool_executed")
    │       ├──► telemetry.log_interaction()
    │       ├──► mascot.on_event('SUCCESS'/'ERROR')
    │       └──► causal_graph.add_edge()
    │
    ▼
Result returned to Gemini → next iteration or response to user
```

### 4.4 Is It Overengineered?

Partially. The `event_bus.py` and `profile_manifest.py` are lightweight but speculative — they were built in response to critique findings about "architectural readiness" rather than immediate need. The `causal_graph.py` is genuinely useful for audit. The `fault_injector.py` is niche (chaos testing only).

**Honest assessment:** ~400 of the 688 LOC in bridge/ are actively useful day-to-day. The rest is architectural insurance.

---

## 5. Critique Implementations

The project underwent 8 rounds of structured critique, each from a different fictional character with a domain specialization. Each critique identified 4 findings; each finding became an implementation item.

### 5.1 Critique Origin

The critique format is:
1. Character profile (name, role, domain focus)
2. 4 findings with severity ratings
3. Each finding has: recommendation, location, implementation plan
4. Todo checklist tracking completion

### 5.2 What Got Built

| Round | Character | Domain | What Was Implemented |
|---|---|---|---|
| V1 | Kira Ivanova | Architecture | Fitness functions (test_architecture_fitness.py), deprecation policy (deprecation.py), singleton audit |
| V2 | Tomas Rivera | DevEx | ww_dev.py (auto-compile on save), error_translator.py, --show-config flag |
| V3 | Maya Krishnan | Product | ActivationFunnel (telemetry.py), TimeToValueTracker, FeatureDiscovery progressive tips |
| V4 | Sam Rivers | Reliability | docs/runbook.md, chaos/ directory, post-mortem template |
| V5 (B1) | Lin Wei | Performance | Performance regression gate, flamegraph profiler, write_batcher.py, memory allocation audit |
| V5 (B2) | Aisha Bakari | Scalability | Parallel tool dispatch, backpressure.py, scalability.md |
| V5 (C1-D3) | Rajesh, Simone, Priya, Helena, Daniel | AI Quality, Data | evaluation.py, sensitivity.py, refusal testing, decomposition.py, CorruptionDetector, CrossSessionRecovery, TTLConfig, CacheWarmer |
| V5 (E1-E3) | Naomi Chen, Tomas Rivera, Amir Hassan | Platform, DevEx, Quality | API versioning, rate limiting, LSP diagnostics, side-by-side diff, anti-pattern scanner, CI quality checks |
| V6 | Ava Chen (Security), Leo Chang (Testing), 18 other characters | Security, Testing, Infra, Docs, Community, Onboarding | MerkleChain, AuditTrail, 21 docs, 7 monitoring scripts, conditional CI, test isolation |

### 5.3 Impact Assessment

**High impact (justified their LOC):**
- evaluation.py, sensitivity.py, refusal testing — directly measurable quality
- CorruptionDetector, CrossSessionRecovery — actual reliability
- API versioning, rate limiting — production necessity
- MerkleChain (logchain.py) — tamper-evident audit trail
- test isolation (pytest-randomly) — catches ordering bugs

**Medium impact (useful but niche):**
- Flame graph profiler, memory allocation audit — performance debugging
- write_batcher.py — marginal gain for DB writes
- FeatureDiscovery progressive tips — activation improvement
- Side-by-side diff — nice terminal UX

**Low impact (critique compliance):**
- profile_manifest.py, capability_registry.py — speculative
- Various documentation files (community governance, gamification, etc.)
- Some scripts (first_commit_tracker.py, mttr_tracker.py) — infrastructure that's not yet wired

### 5.4 Cost Summary

The 8 rounds produced approximately **3,000-3,500 LOC** of implementation across ~40 files. Of that, roughly **2,000 LOC (~60%)** is actively useful, **800 LOC (~25%)** is niche but harmless, and **500 LOC (~15%)** is speculative or ceremonial.

---

## 6. Honest Assessment

| Question | Answer |
|---|---|
| Does it work? | Yes. 391 tests pass, the bridge runs Gemini queries end-to-end. |
| Is it overengineered? | Parts of it, yes. ~500 LOC of speculative architecture, ~500 LOC of ceremonial documentation. |
| Could 2b do this? | 2b has the same core loop. What ww adds is safety (permissions, sandboxing), persistence (checkpoints, telemetry), and developer tooling (diff engine, dashboard, eval). |
| Is the eval framework production-ready? | No. It's useful for regression testing prompt changes but the heuristic scoring is basic. Real eval requires labeled datasets. |
| What's the most valuable feature the original 2b didn't have? | Permission sandboxing + diff engine. Without those, the agent is blind and dangerous. |
