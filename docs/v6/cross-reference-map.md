# Documentation Cross-Reference Map — V6-D1#3

## User-Facing Docs
| Document | Audience | Purpose |
|---|---|---|
| README.md | All | Project overview, quick start |
| docs/getting-started.md | New users | First-time setup and usage |
| docs/troubleshooting.md | All | Common issues and solutions |
| docs/runbook.md | Operators | Incident response procedures |
| docs/deployment-guide.md | DevOps | Production deployment |

## Developer Docs
| Document | Audience | Purpose |
|---|---|---|
| CONTRIBUTING.md | Contributors | How to contribute |
| docs/test-architecture.md | Developers | Test organization |
| docs/scalability.md | Architects | Scaling constraints |
| docs/information-architecture.md | Docs team | Doc organization |
| docs/sli-slo.md | Operators | Service level targets |

## Architecture Docs
| Document | Audience | Purpose |
|---|---|---|
| agents/ | Developers | Agent definitions |
| meta/specs/ | Architects | Specifications |
| ADR files | Architects | Decision records |

## Code-Level Docs
| Source File | Purpose |
|---|---|
| src/gemini_bridge.py | Main orchestrator entry point |
| src/core/memory.py | Memory management and persistence |
| src/tools/registry.py | Tool registration and DAG resolution |
