# Tutorial & Workshop Creation — V6-C4#3

## Purpose
Guide for creating structured tutorials and workshops for WW Bridge, enabling community members to learn and teach effectively.

## Tutorial Format
Each tutorial should include:
1. **Title & Objective** — What the learner will accomplish
2. **Prerequisites** — Required knowledge and setup
3. **Step-by-step instructions** — Numbered steps with code examples
4. **Expected output** — What each step should produce
5. **Checkpoint questions** — Verify understanding
6. **Troubleshooting** — Common issues and fixes

## Existing Tutorial Content
- `src/tutorial.py` — Interactive 7-step CLI tutorial
- `docs/getting-started.md` — Written getting-started guide
- `.tel/tests/test_getting_started.py` — 7 automated tests verifying the tutorial flow

## Workshop Templates

### Beginner Workshop (60 min)
| Segment | Time | Content |
|---------|------|---------|
| Intro | 5 min | What is WW Bridge? Architecture overview |
| Setup | 10 min | Install, configure credentials, first run |
| Core concepts | 15 min | Agent hierarchy, tools, workspace |
| Hands-on | 20 min | Guided exercise: build a tool chain |
| Q&A | 10 min | Open questions, troubleshooting |

### Advanced Workshop (90 min)
| Segment | Time | Content |
|---------|------|---------|
| Architecture deep dive | 15 min | 3-tier agency, event bus, causal graph |
| Custom tools | 20 min | Writing and registering new tools |
| Plugin development | 20 min | Plugin system and lifecycle |
| Production deployment | 20 min | Docker, CI/CD, monitoring |
| Design review | 15 min | Architecture review of participant projects |

## Creating a New Tutorial
1. Copy the template from the `tutorials/` directory
2. Replace content markers with your material
3. Add automated tests in `.tel/tests/`
4. Add to the tutorial index

## Distribution
- Tutorials live in `docs/tutorials/`
- Workshops are published as markdown in `docs/workshops/`
- Community-contributed tutorials are welcome via PR
