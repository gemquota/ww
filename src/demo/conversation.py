"""
Demo mode — canned conversation showing the full agentic workflow.
No credentials needed. Run with: python gemini_bridge.py --demo
"""

DEMO_CONVERSATION = [
    {
        "role": "user",
        "content": "List all Python files in the project"
    },
    {
        "role": "assistant",
        "content": "I'll scan the project directory for Python files.\n\n```tool:read_file\npath: .\n```\n\nHere are all the Python files in the project:\n\n**Source files:**\n- `src/gemini_bridge.py` (698 lines) — Main orchestrator with REPL loop\n- `src/tool_executor.py` (367 lines) — Tool dispatch and delegation\n- `src/config.py` (182 lines) — Configuration management\n- `src/context_manager.py` (328 lines) — Conversation history and token counting\n- `src/smart_context.py` (231 lines) — Git-aware workspace context\n- `src/permissions.py` (219 lines) — Sandbox and approval system\n- `src/checkpoint.py` (219 lines) — Git checkpoint undo system\n- `src/telemetry.py` (182 lines) — Session logging\n- `src/ui_adapter.py` (156 lines) — UI abstraction layer\n- `src/commands.py` (216 lines) — Slash command dispatch\n\n**Core modules:**\n- `src/core/memory.py` (471 lines) — 3-tier memory with SQLite\n- `src/core/healing.py` — Auto-healer\n- `src/core/schemas.py` — Pydantic models\n- `src/core/benchmarker.py` — Benchmark harness\n\n**Tools:**\n- `src/tools/system_tools.py` (329 lines) — 10 tool implementations\n- `src/tools/registry.py` (177 lines) — DAG tool registry\n\n**Test files:** 7 test files with 254 tests total\n\nProject stats: ~5,950 lines of Python across 28 modules"
    },
    {
        "role": "user",
        "content": "Explain the architecture of this project"
    },
    {
        "role": "assistant",
        "content": "# WW Bridge Architecture\n\n## 3-Tier Agent Hierarchy\n\n```\nUser\n  └── Communicator (REPL loop, UI)\n        └── Overseer (technical lead, orchestration)\n              ├── Coders (implementation)\n              ├── Researchers (information gathering)\n              ├── Testers (verification)\n              └── Security (safety checks)\n```\n\n**Communicator** — The TUI layer. Manages the REPL loop, slash commands, and direct tool dispatch. Entry point for all user interaction.\n\n**Overseer** — Technical lead agent. Chains specialist agents in pipelines, collects and processes results, delegates complex multi-step tasks.\n\n**Specialists** — Focused agents (coder, researcher, tester, security) with specific system prompts and tool access.\n\n## Memory System (3-Tier)\n\n| Tier | Name | Content | Persistence |\n|------|------|---------|-------------|\n| A | Hot | Last N verbatim turns | In-memory |\n| B | Facts | Compressed key facts | SQLite + scratchpad |\n| C | Archival | Narrative summaries | SQLite |\n\n## Key Features\n- **Tool Registry**: DAG-based tool dependencies with circular detection\n- **Permissions**: Granular approval system (always/on-request/never)\n- **Checkpoints**: Auto git snapshots with `/undo`\n- **Auto-Healer**: Failure diagnosis via Gemini\n- **Plugins**: Extensible via `WWPlugin` base class\n\n## Data Flow\n\n```\nUser Input → Communicator\n  → Memory Context (Tier A + B + C)\n  → Gemini API\n  → Tool Block Parsing\n  → Tool Execution (direct or via Overseer)\n  → Output → User\n```\n\nTotal: ~5,950 lines of Python, 254 tests, 8 agent definitions, 11 tools."
    },
    {
        "role": "user",
        "content": "Run the test suite"
    },
    {
        "role": "assistant",
        "content": "```tool:shell_exec\ncd /app && python -m pytest .tests/ -q --tb=short\n```\n\n**Test Results: 254 passed in 4.41s**\n\nAll tests pass. Here's the breakdown:\n\n| Test File | Tests | Status |\n|-----------|-------|--------|\n| test_core.py | 20 | ✅ All passed |\n| test_tools.py | 23 | ✅ All passed |\n| test_integration.py | 26 | ✅ All passed |\n| test_set3.py | 17 | ✅ All passed |\n| test_quality_10dim.py | 46 | ✅ All passed |\n| test_systemic_benchmarks.py | 38 | ✅ All passed |\n| test_trend_engine.py | ~10 | ✅ All passed |\n| test_permissions.py | 25 | ✅ All passed |\n| test_telemetry.py | 12 | ✅ All passed |\n| test_tool_executor.py | 15 | ✅ All passed |\n| test_config.py | 8 | ✅ All passed |\n| test_file_watcher.py | 14 | ✅ All passed |\n\nNo failures, no warnings. Full pass."
    },
    {
        "role": "user",
        "content": "Show me the available slash commands"
    },
    {
        "role": "assistant",
        "content": "Available slash commands:\n\n| Command | Description |\n|---------|-------------|\n| `/tokens` | Show token usage stats |\n| `/undo` | Revert last checkpoint |\n| `/compact` | Force memory compaction |\n| `/reload` | Reload bridge and agents |\n| `/init` | Create default agent specs |\n| `/verbose` | Toggle verbose mode |\n| `/history` | Show conversation history |\n| `/memory` | Show memory tier contents |\n| `/save` | Save current session |\n| `/load` | Load a saved session |\n| `/sessions` | List saved sessions |\n| `/export` | Export session as Markdown |\n| `/policy` | Show/change approval policy |\n| `/plugins` | Manage plugins |\n| `/help` | Show this help |\n\nType any command to use it. Commands are processed by the Communicator without going through the LLM."
    }
]


def get_demo_banner() -> str:
    """Return the demo mode welcome banner."""
    return """
  ╭────────────────────────────────────────────────────────────╮
  │  🎪 WW Bridge — DEMO MODE                                 │
  │                                                           │
  │  This is a simulated conversation showing the full        │
  │  agentic workflow. No API credentials needed.             │
  │                                                           │
  │  Features demonstrated:                                   │
  │    • File listing and project analysis                    │
  │    • Architecture explanation with diagrams               │
  │    • Test suite execution via tool blocks                 │
  │    • Slash command system                                 │
  │    • Agent delegation and tool dispatch                   │
  │                                                           │
  │  Type 'next' to advance through the demo,                 │
  │  or 'exit' to leave demo mode.                            │
  │                                                           │
  │  Run without --demo for the real thing.                   │
  ╰────────────────────────────────────────────────────────────╯
"""
