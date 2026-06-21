# Community Governance Model

**Last updated**: 2026-06-20
**Version**: 1.0.0

---

## Overview

WW Bridge follows a **lazy consensus** governance model — decisions are made
by default unless someone objects. This keeps the project moving fast while
ensuring stakeholders can raise concerns.

## Roles

| Role | Privileges | How to attain |
|------|-----------|--------------|
| **Contributor** | Submit PRs, file issues | First accepted PR |
| **Regular Contributor** | Triage issues, review PRs | 5+ merged PRs, demonstrated good judgment |
| **Maintainer** | Merge PRs, manage releases, vote on proposals | Invitation from existing maintainers |
| **Lead Maintainer** | Final call on disputes, publish releases | Unanimous maintainer vote |

## Decision-Making

| Type | Process | Timeframe |
|------|---------|-----------|
| Bug fixes | Lazy consensus | 24 hours |
| Feature additions | Proposal + lazy consensus | 72 hours |
| Breaking changes | RFC + maintainer vote | 1 week |
| Governance changes | RFC + unanimous maintainer vote | 2 weeks |

## RFC Process

1. **Proposal** — Open an issue with the `rfc` label
2. **Discussion** — 5 business days for community input
3. **Resolution** — Maintainer votes, lazy consensus applies
4. **Documentation** — Outcome and rationale recorded in ADR

## Code of Conduct

All participants agree to abide by the project's Code of Conduct:
- Be respectful and inclusive
- Assume good faith
- Focus on what's best for the project and its users
- Address technical arguments, not personal ones

## Conflict Resolution

1. Disagreement → discussion thread
2. Stalemate → maintainer vote
3. Escalation → lead maintainer decision

## Release Governance

- Releases are managed by maintainers
- Semantic versioning (major.minor.patch)
- Breaking changes require major version bump
- Release notes must document all significant changes
