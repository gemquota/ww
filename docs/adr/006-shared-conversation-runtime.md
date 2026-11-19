# ADR-006: Shared conversation runtime

**Status:** Accepted  
**Date:** 2026-11-20

## Context

The terminal CLI, browser dashboard and older agent bridge had separate Gemini clients, registries and execution loops. Features and fixes therefore behaved differently depending on the entry point.

## Decision

The supported terminal and browser clients use one `WWClient` transport and one `ConversationRuntime`. The runtime owns system instructions, tool parsing, schema validation, policy/approval, tool execution, output feedback, round limits and streaming events.

## Consequences

- New interfaces must be adapters over the shared runtime, not new executors.
- Tool behavior and approval policy are consistent across terminal and browser.
- The old `src/gemini_bridge.py` and `src/tool_executor.py` are retired migration source.
- Advanced legacy agent/memory features must be migrated deliberately before reuse.
