# WW documentation index

## Current, authoritative documentation

- [Codebase inventory](codebase-inventory.md): repository footprint, active modules, legacy areas and adversarial findings.

- [Architecture review](architecture-review.md): supported runtime, technical findings, adversarial review and verification limits.
- [Feature-branch integration review](branch-integration-review.md): branch disposition and selective integration decisions.
- [Dashboard API](api/dashboard.md): current authenticated local API and SSE endpoints.
- [Tool system](api/tools.md): registered tools, argument schemas, protocol and approval boundaries.
- [Pages and device API deployment](deployment/github-pages-device-api.md): GitHub Pages frontend with Termux/PRoot backend.
- [Optional Docker deployment](../deploy/README.md): local container setup, not yet device-verified.
- [Architecture decisions](adr/INDEX.md): current ADRs 006–010 and historical ADR status.

## Historical material

- `adr/001`–`adr/005` describe an earlier agent-hierarchy and DAG-executor design.
- `v6/` and `v7/` contain historical quality, operations and refactoring proposals. They are not current implementation specifications.
- Phase 2C isolation/capability-probe documents are historical only. The user explicitly stopped isolation work; PRoot is the execution environment, not a sandbox.
- `.old/2b/` is an archived code snapshot, not an active package.

When a historical document conflicts with the root README, current source, current ADRs or the architecture review, treat the current source and current ADRs as authoritative.
