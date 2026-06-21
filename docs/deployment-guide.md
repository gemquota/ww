# Deployment Guide

Addresses NEW-V6-I3#1 (Ahmed Osman).

## Deployment Options

### 1. Docker (Recommended)

```bash
# Build
docker build -f deploy/Dockerfile -t ww-bridge .

# Run
docker run -it --rm \
  -v $(pwd)/.env:/app/.env \
  -v ww_data:/app/.ww \
  ww-bridge --health

# API mode (with dashboard)
docker run -d --name ww-bridge \
  -p 8080:8080 \
  -v $(pwd)/.env:/app/.env \
  -v ww_data:/app/.ww \
  ww-bridge --serve
```

### 2. Docker Compose

```bash
cd deploy
docker-compose up -d
```

### 3. Terraform

```bash
cd deploy/terraform
terraform init
terraform apply -var="host_port=8080"
```

### 4. Bare Metal

```bash
pip install -r requirements.txt
python gemini_bridge.py --health
```

## Environment Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `SECURE_1PSID` | Yes* | Gemini cookie auth |
| `SECURE_1PSIDTS` | Yes* | Gemini cookie auth |
| `GEMINI_API_KEY` | Yes* | Gemini API key auth |
| `WW_WORKSPACE` | No | Workspace root (default: cwd) |
| `WW_DASHBOARD_API_KEY` | No | API key for dashboard access |

*\*One of cookie or API key auth is required.*

## Health Check

```bash
python gemini_bridge.py --health
```

Or via API: `GET /api/v1/health`

## Monitoring

- Dashboard: `http://localhost:8080/`
- Health endpoint: `GET /api/v1/health`
- Metrics: `GET /api/v1/stats`
- Logs: `.tel/` directory
