# Test Architecture

Addresses NEW-V6-T1#1 (Dr. Leo Chang) and NEW-V6-T2#1 (Maria Tsvetkova).

## Test Categories

| Category | Scope | Framework | Isolation Level | Run Frequency |
|----------|-------|-----------|----------------|---------------|
| Unit | Single function/class | pytest | Function-scope tempdir | Every push |
| Integration | Cross-module workflows | pytest + asyncio | Module-scope tempdir | Every push |
| System | Full REPL + tool dispatch | pytest + mock client | Session-scope tempdir | Every push |
| Quality | Prompt quality, AI safety | pytest | Function-scope | Every push |
| Benchmark | Performance regression | pytest + time | Dedicated env | Nightly |
| Chaos | Fault injection | Python scripts | Dedicated env | Weekly |

## Test Fixture Strategy

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `tmp_path` | function | Per-test temp directory (pytest built-in) |
| `sandbox` | function | Isolated workspace with permission manager |
| `mock_client` | module | Mock Gemini Web API for REPL tests |
| `telemetry_db` | function | Isolated SQLite telemetry database |
| `checkpoint_dir` | function | Isolated checkpoint directory |

## Coverage Targets

| Module Tier | Target | High-Risk Areas |
|-------------|--------|-----------------|
| Core (`src/core/`) | 90%+ | memory, schemas, healing |
| Bridge (`src/bridge/`) | 80%+ | event_bus, causal_graph |
| Tools (`src/tools/`) | 75%+ | system_tools (shell_exec, url_fetch) |
| Utils (`src/utils/`) | 75%+ | web_client, validation |
| Entry (`src/gemini_bridge.py`) | 70%+ | REPL loop, credential handling |

## Test Isolation Rules

1. **No shared state between tests**: each test gets fresh fixtures
2. **No filesystem side effects**: all temp dirs cleaned after test
3. **No network access**: Gemini API calls mocked in integration tests
4. **Deterministic ordering**: tests pass in any order (`pytest-randomly`)
5. **No test interdependencies**: each test can run alone
