# WW Bridge

**Gemini Multi-Agent Bridge** — A production-quality agentic coding harness powered by the Gemini Web API.

## Quick Links

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started.md) | Installation, credentials, first run |
| [Architecture](architecture.md) | System design and component interactions |
| [Commands](commands.md) | All slash commands |
| [Configuration](configuration.md) | All config options and environment variables |
| [Security](security.md) | Sandbox, policies, audit logging |
| [Deployment](deployment.md) | Docker, CI/CD, production |
| [FAQ](faq.md) | Troubleshooting and common issues |
| [Codebase Architecture](codebase-architecture.md) | Module-by-module analysis |

## API Reference

| Module | Description |
|--------|-------------|
| [Bridge API](api/bridge.md) | CLI arguments and main loop |
| [Tool System](api/tools.md) | 11 built-in tools with usage examples |
| [Agent System](api/agents.md) | Multi-agent routing graph with pipeline chains and parallel delegation |
| [Memory System](api/memory.md) | 3-tier context + PCG causal graph |
| [Dashboard API](api/dashboard.md) | FastAPI web dashboard endpoints |
| [Plugin System](api/plugins.md) | Plugin lifecycle and development |
| [Mascot TUI](api/gfx.md) | Terminal mascot animation states |
| [Utilities](api/utils.md) | WebGeminiClient and validation |

## Project Stats

- **Source files**: 28 in `src/` package
- **Tests**: 197 with 100% pass rate
- **Documentation**: 19 files, 1,326 lines
- **Tools**: 11 built-in tools with Pydantic schemas
- **Agents**: 5 specialized roles with cross-delegation and pipeline chaining
- **Deploy**: Docker, docker-compose, CI workflow
