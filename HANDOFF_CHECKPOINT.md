# WW Bridge — Handoff Checkpoint

**Date**: 2026-06-16  
**Directory**: `/data/data/com.termux/files/home/dev/codex/ww`  
**Tests**: `254 passed, 0 failures`  
**Server**: `python3 -m http.server 8765 --bind 127.0.0.1` (running on 8765)

---

## What This Project Is

Python CLI harness for a Gemini-powered multi-agent coding loop. 3-tier agent hierarchy (Communicator → Overseer → Specialists) with SQLite memory, tool execution, and plugin system. ~6,500 lines across 35+ modules. 254 tests.

---

## What Has Been Built

### Architecture Visualization (3 interactive HTML files in `docs/`)
- **`architecture-explorer.html`** — 9-view Cytoscape.js graph of all 35 modules
- **`domain-venn.html`** — 6-view domain visualization suite
- **`domain-refined.html`** — Unified 3-axis domain map (X: Infrastructure→Application, Y: Development→Experience, Color: Spectrum, Size: codebase %)

### Causal Instrumentation
- `src/bridge/causal_graph.py` — `CausalEvent` dataclass + `CausalGraph` with SQLite persistence
- Enhanced `src/bridge/decision_tracer.py` — `start_branch()`, `merge_branch()`, `set_causal_graph()`
- Added `/why <event_id>` CLI command to `src/commands.py`
- Wired causal events into `src/tool_executor.py`
- Added `causal_graph` field to `BridgeContext` in `src/context.py`

### Critiques & Characters
- **44 characters across 11 domains** (4 per domain) — full registry in `critiques/CHARACTER-REGISTRY.md`
- **V5: 16 new characters** with dedicated findings, critiques, and implementation plans — all generated in `critiques/v5/`
- V5 covers: Architecture, DevEx, Product, Reliability, Performance (2), AI Quality (3), Memory (3), Code Gen (3), Ecosystem

### V5 Critiques — COMPLETED ✅
All 16 V4-Extension characters now have:
- Individual critique files (`critiques/v5/{num}-critique.md`)
- Multi-phase implementation plan files (`critiques/v5/{num}-plan.md`)
- `critiques/v5/MASTER.md` summary table
- Each critique has 4 domain-specific findings (HIGH/MEDIUM)
- Each plan has phased implementation (Phase 1: HIGH, Phase 2: MEDIUM, Phase 3: LOW)

### Fixed Bugs
- `gen_v5_critiques.py` had a variable name bug (`characters` used but never defined — `data` was the loaded dict)
- Fixed: changed `for c in characters:` → `for c in data['new_characters']:`
- Script now compiles and runs cleanly

## Constraints
- **`file://` protocol**: All HTML must work when opened directly (no fetch, no CDN)
- **All 254 tests must pass** — `python -m pytest .tests/ -q --tb=short`
- **All files compile** — `python3 -m py_compile src/*.py src/bridge/*.py src/core/*.py src/tools/*.py src/utils/*.py`
- **`.env` has real credentials** — never commit or leak

## Key Files Reference

| File | Purpose |
|------|---------|
| `docs/architecture-explorer.html` | 9-view module graph (Cytoscape) |
| `docs/domain-venn.html` | 6-view domain visualization suite |
| `docs/domain-refined.html` | **Latest**: Unified 3-axis domain map |
| `src/bridge/causal_graph.py` | Causal event + graph |
| `src/bridge/decision_tracer.py` | Enhanced with branching |
| `src/commands.py` | Added `/why` command |
| `src/tool_executor.py` | Wired with causal events |
| `src/context.py` | Added `causal_graph` field |
| `critiques/CHARACTER-REGISTRY.md` | All 44 characters × 11 domains |
| `critiques/v4-extension-characters.json` | 16 new character definitions |
| `critiques/v5/MASTER.md` | V5 master summary (33 files) |
| `gen_v5_critiques.py` | Fixed: now uses `data['new_characters']` |
| `HANDOFF_CHECKPOINT.md` | This file |

## Potential Next Steps
1. Integrate V5 plan findings into actual codebase changes
2. Refine the architecture graphs further (user requested bezier super-group contours, force-directed layout)
3. Run the full pytest suite to ensure 254 passed, 0 failed
4. Continue refining the domain-refined.html with 3-axis semantic positioning
5. Implement the causal instrumentation improvements from V5 plans
