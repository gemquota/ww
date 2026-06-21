# Deployment Guide

## Docker (Recommended)

### Prerequisites
- Docker Engine 24+ and Docker Compose v2+

### Build

```bash
# Build the image
docker compose -f deploy/docker-compose.yml build

# Or build manually
docker build -f deploy/Dockerfile -t ww-bridge .
```

### Run Interactive Mode

```bash
# With docker-compose (recommended)
docker compose -f deploy/docker-compose.yml up ww-bridge

# Or directly
docker run -it --rm \
  -v "$(pwd):/app" \
  --env-file .env \
  ww-bridge
```

### Run Dashboard

```bash
docker compose -f deploy/docker-compose.yml up dashboard
```

### Run Script Mode

```bash
docker compose -f deploy/docker-compose.yml run --rm ww-bridge --script "find all TODO comments"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WW_DASHBOARD_PORT` | `8080` | Dashboard host port |
| `WW_WORKSPACE_MOUNT` | `.` | Workspace directory to mount |
| `WW_CONFIG_MOUNT` | `./config.yaml` | Config file to mount |

## Dockerfile Details

The Dockerfile uses `python:3.13-slim` and installs:
- System: `git`, `curl` (for git checkpoints and health checks)
- Python: all requirements from `requirements.txt`
- Optional: `uvicorn`, `fastapi` (for dashboard)
- Application code via `COPY . .`

Health check pings `http://localhost:8080/health` every 30s.

## Production Considerations

### Persistence
- Sessions persist in the `ww-sessions` Docker volume
- Mount a host directory for workspace access: `-v /host/path:/app`

### Resource Limits
```yaml
services:
  ww-bridge:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
```

### Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name bridge.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Security
- Run with read-only rootfs where possible
- Use `APPARMOR` or `SELinux` profiles for additional sandboxing
- Never expose the bridge directly to the internet without authentication

## CI/CD Integration

```yaml
# GitHub Actions (see deploy/.github/workflows/ci.yml)
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: pytest .tests/ -v
```

The CI pipeline runs:
1. Type checking with `mypy`
2. Linting with `ruff`
3. Syntax checks on all 22+ source files
4. Full test suite (197 tests)
5. Golden benchmark suite (when API keys are available)
