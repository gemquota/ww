# WW Bridge — Architecture Reference

**Last updated**: 2026-06-20  
**Version**: 1.0.0  

> **Interactive visualization available**: Open
> [`architecture-explorer.html`](architecture-explorer.html) in a browser
> for an interactive graph of all 34+ modules with 11 different views.

---

## Overview

WW Bridge is a Python-based CLI harness for a Gemini-powered multi-agent
coding loop. It implements a **3-tier agent hierarchy** with tool execution,
workspace sandboxing, SQLite-persisted memory, and context management.

**Scale**: ~6,500 lines across 35+ modules, 11 tool implementations,
254 passing tests.

---

## Module Inventory (34 Modules)

### Entry Points (2)
| Module | File | Role |
|--------|------|------|
| Root Entry | `/gemini_bridge.py` | Thin 21-line CLI wrapper, parses `--demo/--health/--auth/--verbose` |
| Orchestrator | `src/gemini_bridge.py` | REPL loop, lifecycle, signal handling, tool dispatch |

### UI & Shell (4)
| Module | File | Role |
|--------|------|------|
| Terminal UI | `src/tui.py` | Header, colors, layout helpers |
| UI Adapter | `src/ui_adapter.py` | Abstract UI protocol (Terminal/Silent) |
| UI Utilities | `src/ui_utils.py` | Theme, spinner, folding, MessageLevel |
| Mascot | `src/gfx/mascot_tui.py` | Animated ASCII art mascot |

### Orchestration (4)
| Module | File | Role |
|--------|------|------|
| Bridge Context | `src/context.py` | Centralized shared state |
| Commands | `src/commands.py` | Slash command dispatch (17 commands) |
| Command Tables | `src/command_tables.py` | /task and /plan commands |
| Config | `src/config.py` | Pydantic-settings config loader |
| Permissions | `src/permissions.py` | Sandbox + approval policies |

### Agent System (3)
| Module | File | Role |
|--------|------|------|
| Agent Hierarchy | `agents/*.md` | 8 agent definition files |
| Prompt Templates | `src/prompt_templates.py` | Versioned templates with hash verification |
| Agents Loader | `src/agents_loader.py` | Hierarchical AGENTS.md loader |

### Tool Execution (4)
| Module | File | Role |
|--------|------|------|
| Tool Executor | `src/tool_executor.py` | Dispatch orchestrator + agent delegation |
| Tool Registry | `src/tools/registry.py` | Pydantic-schematized DAG registry |
| System Tools | `src/tools/system_tools.py` | 11 tool implementations |
| Diff Engine | `src/diff_engine.py` | Fuzzy SEARCH/REPLACE |

### Memory & Data (5)
| Module | File | Role |
|--------|------|------|
| Memory Manager | `src/core/memory.py` | 3-tier SQLite + PCG causal graph |
| Context Manager | `src/context_manager.py` | ConversationHistory + RepoMapper + TokenCounter |
| Smart Context | `src/smart_context.py` | Git-aware workspace context |
| Telemetry | `src/telemetry.py` | Session logging (SQLite + JSONL) |
| Checkpoint | `src/checkpoint.py` | Git checkpoint / undo system |

### Bridge Abstractions (5)
| Module | File | Role |
|--------|------|------|
| Event Bus | `src/bridge/event_bus.py` | Pub/sub decoupling |
| Decision Tracer | `src/bridge/decision_tracer.py` | Reasoning chain recorder |
| Capability Registry | `src/bridge/capability_registry.py` | Tool provider abstraction |
| Profile Manifest | `src/bridge/profile_manifest.py` | Agent fingerprint |
| Fault Injector | `src/bridge/fault_injector.py` | Testing fault injection |

### Plugin System (1)
| Module | File | Role |
|--------|------|------|
| Plugin System | `src/plugins/ww_plugin.py` | Lifecycle + capability permissions |

### API & SDK (5)
| Module | File | Role |
|--------|------|------|
| Dashboard API | `src/dashboard/app.py` | FastAPI REST API |
| Python SDK | `src/ww_client.py` | Async context manager SDK |
| Web Client | `src/utils/web_client.py` | Dual-auth Gemini client + CircuitBreaker |
| Validation | `src/utils/validation.py` | Tool call extraction + error classification |
| File Watcher | `src/file_watcher.py` | Filesystem change detector |
| Demo | `src/demo/conversation.py` | Canned demo conversation |

---

## Agent Hierarchy

```
                      ┌──────────────────────┐
                      │    COMMUNICATOR       │  ← Direct pass-through
                      │  (Entry / UI)         │    to ALL agents
                      └──┬──┬──┬──┬──┬──┬────┘
                ┌────────┘  │  │  │  │  │
                ▼           ▼  ▼  ▼  ▼  ▼
          ┌────────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
          │OVERSEER│ │CODER│ │RECH│ │TEST│ │SEC │ │ARCH│
          └────┬───┘ └────┘ └────┘ └────┘ └────┘ └────┘
     ┌─────────┼─────────────────────────────────┐
     ▼         ▼          ▼          ▼          ▼
┌────────┐ ┌────┐ ┌────────┐ ┌────┐ ┌────┐
│ CODER  │ │RECH│ │ TESTER │ │SEC │ │ARCH│  ← Overseer pipelines
└────────┘ └────┘ └────────┘ └────┘ └────┘    any specialist
     │   Specialist ↔ Specialist lateral edges
     └────────────────────────────────────────┘

◆ Communicator → Direct pass-through to all agents (incl. Overseer)
◆ Overseer → Pipelines specialists, chains I/O, collects results
◆ Collect Pattern: Two agents → processor → third → Overseer
◆ Chain Pattern: Coder → Tester → Security → Overseer
◆ Results flow upward (particles go out the top)
```

---

## Data Flow

```
User Input
    │
    ▼
┌─────────────────────────────────────┐
│ REPL Loop (gemini_bridge.py)        │
│  1. Augment with memory context      │
│  2. Send to Gemini (web_client)      │
│  3. Parse tool: blocks               │
│  4. Dispatch to ToolExecutor          │
│  5. Execute tool (system_tools)       │
│  6. Log to telemetry                 │
│  7. Update memory (3-tier)           │
│  8. Render response                  │
└─────────────────────────────────────┘
    │
    ▼
Response to user
```

---

## Architecture Decisions

| ADR | Title | Summary |
|-----|-------|---------|
| 001 | Agent Hierarchy | 3-tier with Communicator→Overseer→Specialists |
| 002 | Memory Tiers | Hot→Facts→Summary with PCG causal graph |
| 003 | Tool Registry | Pydantic-schematized with DAG dependency resolution |
| 004 | Gemini Web API | Dual auth (API key + cookie) for Google Gemini |
| 005 | Checkpoint System | Git-based snapshots with /undo support |

See [docs/adr/](adr/) for full details.

---

## Interactive Visualization

Open **[architecture-explorer.html](architecture-explorer.html)** in a browser
to explore all modules interactively with 11 different graph views:

| View | Description |
|------|-------------|
| 🚀 Intro | Core modules starting point |
| 🎯 Venn | Semantic groupings with overlapping concerns |
| 🔀 Pipeline | Query data flow (left to right) |
| 📦 Groups | Compound node grouping |
| 📦 Layers | 10 architectural layers |
| 🔗 Deps | Concentric dependency hubs |
| 📐 Grid | Space distribution map |
| 🔮 Clusters | Algorithmic clustering |
| 🌳 Tree | 3-level hierarchy tree |
| 🎯 Radial | Radial by layer |
| 🤖 Agents | Agent communication patterns |

---

## See Also

- [Interactive Architecture Explorer](architecture-explorer.html) — start here
- [Static SVG Diagram](architecture.svg) — printable overview
- [Getting Started Guide](getting-started.md)
- [Commands Reference](commands.md)
- [Security Model](security.md)
- [Troubleshooting](troubleshooting.md)
