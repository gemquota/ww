# Development

**Last updated**: 2026-06-20  
**Version**: 1.0.0  

## Project Structure

```
ww/
├── gemini_bridge.py       # Main orchestrator
├── config.yaml            # Runtime configuration
├── config.py              # Pydantic-settings config loader
├── core/                  # schemas, memory, healing, benchmarker, judge
├── tools/                 # registry, system_tools (11 tools)
├── utils/                 # web_client, validation
├── dashboard/             # FastAPI web dashboard
├── plugins/               # Plugin system
├── gfx/                   # Mascot TUI
├── benchmarks/            # quality_bench.py, golden_tasks, DAG
├── benchmark_results/     # Archived results
├── tests/                 # 85 unit tests + 47 quality tests
├── meta/                  # Analysis, tasks, porting record
├── agents/                # 8 agent markdown definitions
└── docs/                  # Documentation site
```

## Code Style

- Python 3.10+ with asyncio patterns
- Type hints for all function signatures
- Prefer `pathlib.Path` over `os.path`
- Use structured tool blocks (`tool:xxx`) for all system interaction
- Follow ruff linting (120 char line limit)

## Running Tests

```bash
# Syntax check
python -m py_compile gemini_bridge.py config.py core/*.py tools/*.py utils/*.py

# Unit tests (85 tests)
python3 -m pytest tests/ -v

# Quality tests (47 tests)
python3 -m pytest tests/test_quality_10dim.py -v

# Sandbox verification
python3 -c "from permissions import Sandbox; s=Sandbox('/app'); s.assert_safe_path('/etc/passwd')"
```

## Adding a New Tool

1. Define args schema in `tools/system_tools.py` (Pydantic model)
2. Implement the tool function
3. Register in `ToolRegistry` at bottom of `tools/system_tools.py`
4. Add import and registration in `gemini_bridge.py`
5. Write tests in `tests/test_tools.py`

## Building Documentation

```bash
mkdocs serve    # Dev server at http://localhost:8000
mkdocs build    # Static site to site/
```

## Docker

```bash
docker compose build
docker compose up -d
docker compose logs -f
```
