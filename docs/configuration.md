# Configuration

**Last updated**: 2026-06-20  
**Version**: 1.0.0  

## File-Based Configuration (`config.yaml`)

```yaml
workspace: "."
session: "default"
verbose: false
context_window: 128000
policy: "on-request"
max_file_size_kb: 512

gemini:
  timeout: 45
  max_retries: 3
  rate_limit_rpm: 10

memory:
  max_tier_a: 20
  compress_threshold: 50
  session_name: "default"
  max_checkpoint_count: 20

dashboard:
  host: "0.0.0.0"
  port: 8080
  log_level: "info"

plugins:
  directory: "plugins"
  auto_load: true

logging:
  level: "INFO"
```

## Environment Variable Overrides

All config values can be overridden via environment variables with the `WW_` prefix:

| Env Variable | Config Path | Example |
|-------------|-------------|---------|
| `WW_WORKSPACE` | `workspace` | `WW_WORKSPACE=/app` |
| `WW_VERBOSE` | `verbose` | `WW_VERBOSE=true` |
| `WW_CONTEXT_WINDOW` | `context_window` | `WW_CONTEXT_WINDOW=64000` |
| `WW_POLICY` | `policy` | `WW_POLICY=on-confirm` |
| `WW_GEMINI__TIMEOUT` | `gemini.timeout` | `WW_GEMINI__TIMEOUT=60` |
| `WW_GEMINI__MAX_RETRIES` | `gemini.max_retries` | `WW_GEMINI__MAX_RETRIES=5` |
| `WW_GEMINI__RATE_LIMIT_RPM` | `gemini.rate_limit_rpm` | `WW_GEMINI__RATE_LIMIT_RPM=15` |
| `WW_DASHBOARD__HOST` | `dashboard.host` | `WW_DASHBOARD__HOST=127.0.0.1` |
| `WW_DASHBOARD__PORT` | `dashboard.port` | `WW_DASHBOARD__PORT=9090` |
| `WW_MEMORY__MAX_TIER_A` | `memory.max_tier_a` | `WW_MEMORY__MAX_TIER_A=50` |
| `WW_MEMORY__MAX_CHECKPOINT_COUNT` | `memory.max_checkpoint_count` | `WW_MEMORY__MAX_CHECKPOINT_COUNT=50` |
| `WW_MAX_FILE_SIZE_KB` | `max_file_size_kb` | `WW_MAX_FILE_SIZE_KB=1024` |

## Credentials

Credentials are loaded from `.env` in the project root:

```
SECURE_1PSID=your_value_here
SECURE_1PSIDTS=your_value_here
```

## Config Loading Order

1. Default values in `config.py`
2. Values from `config.yaml` (or `$WW_CONFIG` path)
3. Environment variable overrides (`WW_*`)
4. CLI arguments (`--script`, `--session`, `--verbose`)
