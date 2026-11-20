# Architecture Decision Records

**Current architecture review:** 2026-11-20

ADRs 001–005 record an earlier agent-hierarchy architecture. They remain useful historical context but do not describe the supported terminal/browser runtime in full.

## Historical decisions

| ADR | Decision | Current status |
|---|---|---|
| 001 | Communicator → Overseer → Specialists agent hierarchy | Deprecated; legacy migration source only |
| 002 | Hot → Facts → Summary memory tiers | Legacy; not part of the supported runtime |
| 003 | Tool registry with DAG dependencies | Superseded by the shared schema-validated ToolRegistry; DAG executor is retired |
| 004 | Gemini Web API as model interface | Accepted in principle; implemented through the supported gemini-webapi WWClient |
| 005 | Git-based checkpoint undo | Legacy subsystem; not part of the default runtime |

## Current decisions

| ADR | Decision | Status |
|---|---|---|
| 006 | One shared ConversationRuntime for terminal and browser | Accepted |
| 007 | PRoot-Distro is the execution environment, not a security sandbox | Accepted |
| 008 | Static GitHub Pages client with device-hosted local API | Accepted |
| 009 | Local approval for privileged model-generated tools | Accepted |
| 010 | URL fetching remains disabled until DNS/redirect protections exist | Accepted |

## ADR format

Each record captures context, decision, consequences and rejected alternatives. Update an ADR when implementation changes; do not leave a historical proposal labelled as the active architecture.
