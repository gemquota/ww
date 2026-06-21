# Contributing to WW Bridge

Addresses NEW-V6-C1 through NEW-V6-C4 (Community & Open Source).

## Welcome!

Thank you for considering contributing to WW Bridge. This document outlines
the contribution pathways, expectations, and processes.

## Contributor Levels

| Level | Description | Requirements |
|-------|-------------|--------------|
| **First-time** | First contribution | Submit a PR |
| **Repeat** | Multiple contributions | 2+ merged PRs |
| **Regular** | Consistent contributor | 10+ merged PRs |
| **Maintainer** | Core team member | Invitation after sustained contribution |

## Getting Started

1. Read the [README.md](README.md) for project overview
2. Set up your development environment (see below)
3. Look for issues tagged `good-first-issue` 
4. Join our community discussions

## Development Environment

```bash
# One-command bootstrap
make setup
```

Or manually:

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your credentials
python gemini_bridge.py --health  # Verify setup
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Run the test suite: `python -m pytest .tests/ -q`
4. Ensure all source files compile: `python -m py_compile src/*.py`
5. Submit a PR with a description of changes

## Code Standards

- Python 3.10+ with type hints
- Follow existing code style (ruff config)
- Include tests for new functionality
- Update documentation for API changes

## PR Review SLAs

| Review Type | Target |
|-------------|--------|
| Initial review | Within 48 hours |
| Follow-up review | Within 24 hours |
| Merged PR (if approved) | Within 1 week |

## Developer Certificate of Origin

All commits must include a DCO sign-off:

```
git commit -s -m "feat: add new feature"
```

This certifies that you have the right to submit the contribution
under the project's license. The CI enforces DCO check.

## Issue Triage

- Bug reports are triaged daily
- Priority = Impact × Frequency
- Issues tagged `good-first-issue` are beginner-friendly with mentor support

## Community

- **Discussions**: GitHub Discussions
- **Chat**: Discord (link in README)
- **Office hours**: Monthly maintainer Q&A

## License

By contributing, you agree that your contributions will be licensed
under the project's MIT License.
