# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the WW Bridge project.

Each ADR documents a significant architectural decision, including the context,
options considered, and the rationale for the chosen approach.

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| 001 | [3-Tier Agent Hierarchy](001-agent-hierarchy.md) | Accepted |
| 002 | [Three-Tier Memory System](002-memory-tiers.md) | Accepted |
| 003 | [DAG-Based Tool Registry](003-tool-registry.md) | Accepted |
| 004 | [Gemini Web API Choice](004-gemini-web-api.md) | Accepted |
| 005 | [Git-Based Checkpoint System](005-checkpoint-system.md) | Accepted |

## Template

When proposing a new ADR, use the following template:

```markdown
# ADR-NNN: Title

**Status**: Proposed | Accepted | Deprecated | Superseded
**Date**: YYYY-MM-DD

## Context
What is the issue motivating this decision?

## Decision
What is the change being proposed?

## Consequences
What becomes easier or harder?
```
