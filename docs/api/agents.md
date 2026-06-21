# Agent System

WW implements a multi-agent routing architecture that enables pipeline chains, parallel fan-out, and cross-delegation between agents.

## Architecture

The agent system is a **flexible multi-agent routing graph**, not a rigid hierarchy.
Any agent can delegate to any other agent, enabling dynamic pipeline chains,
parallel fan-out, and collaborative multi-agent feedback loops.

```
                          ┌──────────────────────┐
                          │     COMMUNICATOR      │
                          └──────────┬───────────┘
                                     │  spine 1
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
    ┌────┴──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌───┴────┐
    │ OVERSEER  │──│ CODER│──│RESRCH│──│TESTER│──│SECURE│──│ARCHITCT│
    │(Tech Lead)│  │      │  │      │  │      │  │      │  │        │
    └────┬──────┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └───┬────┘
         │  spine 2   │         │         │         │          │
         │      ┌─────┼─────────┼─────────┼─────────┼──────┐   │
         │      │     │         │         │         │      │   │
    ┌────┴────┐ │┌───┴────┐ ┌──┴────┐ ┌──┴────┐ ┌──┴────┐ │ ┌─┴──────┐
    │  CODER  │─││RESEARCH│─│ TESTER│─│SECURE │─│ARCHTCT│─│─│ (more)  │
    └─────────┘ │└────────┘ └───────┘ └───────┘ └───────┘ │ └────────┘
                └──────────────────────────────────────────┘

    Delegation/reference flows down spines and across rows.
    Results flow back up (particles go out the top).
    Any agent can delegate to any neighbor — horizontally or vertically.
```

## Roles

### Communicator (Tier 1 — Entry Point)
- Routes user requests to the appropriate agent
- Delegates complex tasks to the **Overseer**
- Delegates simple, well-defined tasks **directly to specialists** (bypassing Overseer)
- Presents final results to the user

### Overseer (Tier 2 — Technical Lead)
- Receives requirements from the Communicator
- Breaks down complex tasks into sub-tasks
- Routes sub-tasks to specialists using any combination of:
  - **Individual delegation**: Single specialist handles one sub-task
  - **Parallel fan-out**: Multiple specialists receive independent sub-tasks
  - **Pipeline chains**: Output of one specialist feeds into another
  - **Collect-process-fan**: Gather results, process, then pass to another specialist pair
  - **Feedback loops**: Two specialists feed into a third, output goes back to Overseer
- Validates completed work (runs tests, lint)
- Reports technical summaries back to the Communicator

### Specialists (Tier 3 — Execution)
- Execute concrete tasks using tool blocks
- May delegate to **other specialists** for cross-cutting concerns
  (e.g., coder delegates to security for vulnerability review)
- Each specialist maintains its own persistent session context

## Tier 1: Communicator

The Communicator is the user-facing entry point. It:
- Receives natural language requests
- Frames the task for the Overseer
- Delegates to the Overseer via `tool:delegate`
- Reports final results back to the user

**Identity**: "You are the COMMUNICATOR — the user's primary interface."

## Tier 2: Overseer

The Overseer is the technical lead. It:
- Breaks user requirements into sub-tasks
- Delegates to specialized agents via `tool:delegate`
- Validates completed work with `tool:shell` (run tests, lint)
- Reports technical summaries back to the Communicator

**Identity**: "You are the OVERSEER — the internal Technical Lead."

## Tier 3: Specialists

Five specialized agents handle concrete execution:

| Agent | Expertise | Primary Tools |
|-------|-----------|---------------|
| **Coder** | Implementation, refactoring, bug fixes | `tool:write`, `tool:replace`, `tool:read`, `tool:shell` |
| **Researcher** | Codebase exploration, dependency analysis | `tool:search`, `tool:list`, `tool:read`, `tool:focus` |
| **Architect** | System design, file layout planning | `tool:read`, `tool:list`, `tool:focus` |
| **Tester** | Test writing, behavior verification | `tool:shell` (pytest), `tool:write`, `tool:read` |
| **Security** | Vulnerability scanning, credential safety | `tool:search`, `tool:read`, `tool:shell` |

## Agent Markdown Files

Agent definitions are stored as Markdown files in `agents/`:

```
agents/
├── communicator.md    # Tier 1: Entry point behavior
├── overseer.md        # Tier 2: Technical lead protocol
├── coder.md           # Tier 3: Implementation specialist
├── researcher.md      # Tier 3: Code exploration
├── architect.md       # Tier 3: System design
├── tester.md          # Tier 3: Test verification
├── security.md        # Tier 3: Security auditing
└── specialized.md     # Combined specialist definitions
```

Each file is loaded by `agents_loader.py` using the AGENTS.md standard,
supporting hierarchical instruction merging from global → project → subdirectory.

## Delegation Syntax

Agents use a structured block format to delegate tasks:

```tool:delegate
agent: coder
task: Implement error handling in src/permissions.py
```

The ToolExecutor parses these blocks and spawns a sub-session with
the target agent's instructions loaded into system context.

## Custom Agents

To add a custom agent:
1. Create `agents/<name>.md` with the agent's instructions
2. Reference it in `agents/overseer.md` AVAILABLE SPECIALISTS table
3. The `agents_loader.py` will discover it automatically
