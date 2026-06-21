# Observability Stack — V6-I2#3

## Three Pillars

### 1. Logging (Telemetry)
- All agent actions logged to SQLite
- Merkle chain for tamper-evident audit
- Log levels: DEBUG, INFO, WARNING, ERROR
- Structured JSONL format for log parsing

### 2. Metrics (Dashboard)
- `/api/v1/stats/metering` — request rate, active sessions
- `/api/v1/stats` — tool usage breakdown
- DORA metrics: deployment frequency, lead time
- Health endpoint: `/health`

### 3. Tracing (Debug)
- Per-session interaction traces
- Tool execution timing
- Context window usage tracking
- Token consumption monitoring

## Recommended Tools
| Tool | Purpose | Integration |
|---|---|---|
| Prometheus | Metrics collection | Custom endpoint |
| Grafana | Dashboard visualization | Prometheus data source |
| Loki | Log aggregation | JSONL ingestion |
| Jaeger | Distributed tracing | OpenTelemetry export |
