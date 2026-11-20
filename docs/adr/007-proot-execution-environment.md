# ADR-007: PRoot is the execution environment, not a sandbox

**Status:** Accepted  
**Date:** 2026-11-20

## Context

The Android Termux environment does not provide the namespace, cgroup or capability model required for a hardened sandbox. Further isolation probing was explicitly abandoned.

## Decision

Use Debian PRoot-Distro as a compatibility and execution environment for WW. Do not claim that PRoot provides hostile-code containment, separate kernel identities, or independent filesystem/network isolation.

## Consequences

- Commands run with the permissions of the backend process.
- Local approval remains required for writes, patches, Git mutations and shell commands.
- Timeout, output bounds, process-group cleanup and workspace path handling remain important reliability controls, not a sandbox.
- Do not resume Bubblewrap, namespace or cgroup work unless the user explicitly asks.
