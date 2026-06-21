# Architecture Decision Records (ADRs)

**Last updated**: 2026-06-20
**Version**: 1.0.0

---

## What is an ADR?

An Architecture Decision Record captures a significant architectural decision
along with its context, consequences, and alternatives considered.

## Active ADRs

| # | Title | Status | Date |
|---|-------|--------|------|
| 001 | Agent Hierarchy (Communicator → Overseer → Specialists) | ✅ Accepted | 2026-06-09 |
| 002 | Memory Tiers (Hot → Facts → Summary) | ✅ Accepted | 2026-06-09 |
| 003 | Tool Registry with DAG Dependencies | ✅ Accepted | 2026-06-10 |
| 004 | Gemini Web API as Primary Model Interface | ✅ Accepted | 2026-06-10 |
| 005 | Checkpoint System with Git-Based Undo | ✅ Accepted | 2026-06-11 |

## ADR Format

```markdown
# ADR-XXX: Title

**Status**: [Proposed | Accepted | Deprecated | Superseded]
**Date**: YYYY-MM-DD

## Context
_What is the issue motivating this decision?_

## Decision
_What is the change being proposed?_

## Consequences
_What becomes easier or harder after this change?_

## Alternatives Considered
_What other options were evaluated and why were they rejected?_
```

## Guidelines

1. ADRs are numbered sequentially
2. Create a new ADR before implementing a significant architectural change
3. Update ADR status when decisions change
4. Link related ADRs using `Superseded-By` or `Amended-By` headers
