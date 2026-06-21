# WW Module Merging & Deletion Proposal

## Current State
- **78 modules** total in src/ (excluding \_\_init\_\_.py package markers)
- **36 active** (reachable from gemini_bridge/tool_executor) = 7,211 lines (63%)
- **42 unused** (dead code) = 4,301 lines (37%)
- **19 v7 modules** (entirely dead, never integrated)

---

## Phase 1: DELETE (no merge — truly dead code)

### v7/ entire directory — 19 modules, ~1,200 lines
Created for cancelled critiques V7/V8. Never imported anywhere.
→ DELETE src/v7/

### core/ Critique Backfill — 20 modules, ~2,100 lines
Built during critique cycles, never wired into the active runtime:

| Module | Lines | Why Dead |
|--------|-------|----------|
| core.agent_protocol | 97 | Agent protocol spec, never implemented |
| core.api_keys | 130 | Superseded by web_client auth |
| core.architecture_fitness | 110 | Architecture evaluation, never called |
| core.ast_validation | 141 | AST checks, superseded by py_compile |
| core.benchmarker | 148 | Moved to .tel/benchmarks/ |
| core.cache_ttl | 117 | Cache tuning, never integrated |
| core.db | 44 | Standalone DB helper, unused |
| core.decomposition | 100 | Module decomposition analysis |
| core.edit_tracker | 110 | Edit history, never wired |
| core.evaluation | 145 | Evaluation framework, never called |
| core.incident_response | 134 | Incident handling scaffold |
| core.judge | 50 | Evaluation judge, never called |
| core.logchain | 265 | Log chain, superseded by telemetry |
| core.lsp_diagnostics | 114 | LSP integration, never called |
| core.memory_audit | 98 | Memory audit tool |
| core.metrics | 92 | Metric collection, never wired |
| core.postgen | 91 | Post-generation processing |
| core.profiler | 109 | Profiler, superseded by profiler.py |
| core.startup_optimizer | 93 | Startup optimization |
| core.test_coverage | 79 | Test coverage analysis |
| core.ux_patterns | 119 | UX pattern library |

### Standalone Orphans — 7 modules, ~1,000 lines
| Module | Lines | Why Dead |
|--------|-------|----------|
| utils.diff_renderer | 123 | Diff rendering, never imported |
| utils.write_batcher | 72 | Batch writes, never imported |
| utils.sensitivity | 137 | Sensitivity analysis, never imported |
| plugins.ww_plugin | 227 | Plugin system scaffold, never wired |
| demo.conversation | 64 | Demo mode, CLI flag exists but broken |
| tutorial | 113 | Tutorial, never surfaced |
| profiler | 95 | Standalone profiler, unused |

### Dashboard (separate process, keep but isolate) — 3 modules
dashboard.app (343L), dashboard.db (28L), dashboard.routes_auth (54L)
→ Move to deploy/dashboard/ — it's a separate Flask/FastAPI service

---

## Phase 2: MERGE (consolidate related modules)

### Merge 1: bridge/ into core/patterns/
6 modules (causal_graph, decision_tracer, event_bus, fault_injector,
profile_manifest, capability_registry) — architectural patterns
→ src/core/patterns/

### Merge 2: utils/ into callers
utils.validation → tool_executor (only caller)
utils.web_client → gemini_bridge (only caller)
utils.error_translator → gemini_bridge (only caller)
utils.deprecation → gemini_bridge (only caller)

### Merge 3: Consolidate context modules
context.py (133L) + context_manager.py (329L) + smart_context.py (232L)
→ Single src/core/context.py

### Merge 4: Merge small UI modules
ui_adapter.py (157L) + ui_utils.py (218L) → src/ui.py
commands.py (44L) + command_tables.py (64L) → src/commands.py

### Merge 5: Merge small tool files
tools.args.py (76L) + tools.workspace.py (20L) → tools/system_tools.py
tools.registry.py (178L) — stays

---

## Phase 3: RENAME (for clarity)

- src/gemini_bridge.py → src/orchestrator.py
- src/tool_executor.py → src/executor.py
- src/telemetry.py → src/observability.py
- src/permissions.py → src/security.py
- src/_constants.py → src/constants.py

---

## Summary of Impact

| Metric | Before | After |
|--------|--------|-------|
| Total modules | 78 (+19 v7) | ~28 |
| Total lines | 11,512 (+1,200 v7) | ~5,800 |
| Active code % | 63% | ~95%+ |
| Module count reduction | — | ~70% |
| Lines of dead code removed | — | ~5,500 |

---

## Execution Plan

1. Delete all Phase 1 modules (batch removal)
2. Move dashboard to deploy/dashboard/
3. Apply Merge 3 (context consolidation)
4. Apply Merge 4 (UI consolidation)
5. Apply Merge 5 (tool consolidation)
6. Apply Merge 1 (bridge → core/patterns/)
7. Apply Merge 2 (utils → callers)
8. Apply Phase 3 renames
9. Update all imports in entry points
10. Update tests for new paths
11. Rebuild architecture explorer
12. Run full test suite
13. Commit batch
