# ADR-001: 3-Tier Agent Hierarchy

**Status**: Accepted
**Date**: 2025-01-15

## Context

The WW Bridge needs to orchestrate multiple LLM agents with different
responsibilities. The simplest approach is a single agent that does everything,
but this leads to prompt bloat and role confusion. The most complex approach
is a flat swarm of independent agents, which introduces coordination overhead.

## Decision

Use a 3-tier hierarchy:

```
Communicator (UI/Entry)
  └── Overseer (Technical Lead)
        ├── Coder
        ├── Researcher
        ├── Tester
        └── Security
```

- **Communicator**: Manages the TUI, slash commands, and direct tool dispatch
- **Overseer**: Chains specialist agents in pipelines, collects results, delegates
- **Specialists**: Focused single-purpose agents with specific system prompts

The Communicator can also dispatch tools directly without going through the
Overseer for simple operations (read_file, list_dir, etc.)

## Consequences

**Positive**:
- Clear separation of concerns at each tier
- Specialists can be added/removed independently
- The Overseer can implement complex multi-step workflows

**Negative**:
- Extra latency when the Overseer must coordinate multiple specialists
- More complex error handling across tiers

## Alternatives Considered

1. **Single monolithic agent**: Simpler but no role specialization
2. **Flat swarm**: Maximum flexibility but high coordination overhead
3. **Two-tier (User + Agent)**: Too simple for complex multi-step tasks
