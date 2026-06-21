# Multi-Environment Strategy — V6-I3#2

## Environments

| Environment | Purpose | Configuration | URL |
|---|---|---|---|
| dev | Local development | Local SQLite, debug logging | localhost:8080 |
| staging | Pre-release testing | Separate DB, API sandbox | staging.ww-bridge.dev |
| production | Live service | Production DB, rate limiting | api.ww-bridge.dev |

## Promotion Flow
1. Feature developed on `dev` environment
2. Feature deployed to `staging` for validation
3. After test pass → promoted to `production`

## Configuration Differences
```yaml
# config.yaml
dev:
  log_level: DEBUG
  rate_limit: 1000/min
  checkpoint_enabled: true

staging:
  log_level: INFO
  rate_limit: 200/min
  checkpoint_enabled: true

production:
  log_level: WARNING
  rate_limit: 100/min
  checkpoint_enabled: true
```
