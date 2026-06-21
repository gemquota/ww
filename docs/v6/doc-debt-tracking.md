# Documentation Debt Tracking — V6-D2#1

## Process
Track documentation quality alongside code quality.

### Debt Register
| Doc | Current State | Target State | Owner | Priority |
|---|---|---|---|---|
| README.md | ✅ Complete | - | - | - |
| getting-started.md | ✅ Complete | - | - | - |
| troubleshooting.md | ✅ Complete | - | - | - |
| api/ | ⚠️ Partial | Full API reference | TBD | Medium |
| architecture.md | ❌ Missing | Architecture overview | TBD | High |
| tutorials/ | ❌ Missing | 3 tutorials | TBD | Medium |

## Quality Gates
- PRs with doc changes: MUST pass markdownlint
- New features: MUST include doc update
- API changes: MUST update API reference

## Review Cycle
- Monthly: Check debt register, update status
- Quarterly: Full documentation audit
- Per-release: Verify all changed features documented
