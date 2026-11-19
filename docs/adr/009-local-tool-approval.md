# ADR-009: Local approval for privileged tools

**Status:** Accepted  
**Date:** 2026-11-20

## Context

Model-generated shell and file operations can have significant effects on the user's workspace and device.

## Decision

Read-only tools may run without prompting. File writes, patches, Git mutations and shell commands require approval through the backend's local terminal controller. Approval is bound to the normalized tool and validated arguments, and decisions/outcomes are recorded in the local audit log.

## Consequences

- The browser displays the pending operation but does not silently approve it.
- The backend must retain interactive terminal stdin for privileged browser tool calls.
- A disconnected browser does not turn privileged operations into unattended operations.
- This approval model does not replace a security sandbox; PRoot is not one.
