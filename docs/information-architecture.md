# Information Architecture

**Last updated**: 2026-06-20
**Version**: 1.0.0

---

## Overview

This document describes how WW Bridge organizes, stores, and retrieves
information across its various subsystems.

## Documentation Map

```
docs/
├── index.md                     # Entry point / landing
├── getting-started.md           # First-time user guide
├── architecture.md              # System architecture
├── configuration.md             # Configuration reference
├── development.md               # Developer guide
├── deployment-guide.md          # Deployment instructions
├── troubleshooting.md           # Common issues & solutions
├── commands.md                  # CLI command reference
├── security.md                  # Security model
├── scalability.md               # Performance & scaling
├── memory-durability.md         # Memory/storage guarantees
├── test-architecture.md         # Test structure & strategy
├── runbook.md                   # Operations runbook
├── post-mortem-template.md      # Incident post-mortem template
├── sli-slo.md                   # SLI/SLO definitions
├── benchmarks.md                # Benchmark results
├── information-architecture.md  # This file
├── adr/                         # Architecture Decision Records
│   └── INDEX.md
├── api/                         # API documentation
├── v6/                          # V6 critique docs
└── vendor/                      # Third-party docs
```

## Key Principles

1. **Single source of truth** — Each concept documented in exactly one place
2. **Progressive disclosure** — Start simple, link to deeper detail
3. **Testable documentation** — Docs should be verifiable (see `test_getting_started.py`)
4. **Versioned** — Every doc has a last-updated timestamp and version

## Search Strategy

- Use `grep -rn "topic" docs/` for local search
- Build docs site with: `mkdocs build` (config in `config/mkdocs.yml`)
- Generated site available at `site/`

## Cross-Reference Map

| Document | Related Docs | ADRs |
|----------|-------------|------|
| `getting-started.md` | `configuration.md`, `troubleshooting.md` | — |
| `architecture.md` | `scalability.md`, `development.md` | 001, 002, 003 |
| `configuration.md` | `getting-started.md`, `security.md` | — |
| `security.md` | `configuration.md`, `deployment-guide.md` | — |
| `development.md` | `test-architecture.md`, `CONTRIBUTING.md` | — |
| `deployment-guide.md` | `security.md`, `runbook.md` | 004, 005 |
| `runbook.md` | `troubleshooting.md`, `post-mortem-template.md` | — |
| `test-architecture.md` | `development.md`, `benchmarks.md` | — |
