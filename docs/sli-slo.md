# SLIs, SLOs & On-Call

Addresses NEW-V6-I2#1 (Yuki Tanaka).

## Service Level Indicators (SLIs)

| SLI | Definition | Measurement |
|-----|-----------|-------------|
| Request latency (p50) | Median time to respond to a user query | Measured from REPL input to first output |
| Request latency (p95) | 95th percentile response time | Same measurement |
| Error rate | Ratio of failed tool executions | Failed / total tool calls |
| Availability | Uptime of the event loop | Heartbeat every 60s |
| Freshness | Time to persist session state | Measured fsync delay |

## Service Level Objectives (SLOs)

| SLO | Target | Measurement Window |
|-----|--------|-------------------|
| p50 latency < 2s | 99% | 30 days |
| p95 latency < 10s | 95% | 30 days |
| Error rate < 5% | 99% | 7 days |
| Availability > 99.5% | 99.9% | 30 days |
| Freshness < 5s | 99% | 7 days |

## On-Call Runbook

### Severity Definitions

| Sev | Definition | Response Time |
|-----|-----------|--------------|
| SEV1 | Complete outage: no user can use the bridge | 15 min |
| SEV2 | Partial outage: feature broken but core works | 60 min |
| SEV3 | Minor issue: cosmetic, non-critical | Next business day |
| SEV4 | Question / low priority | Within 1 week |

### Escalation Path

1. **Primary on-call**: First responder, handles SEV3/SEV4
2. **Secondary on-call**: Backup for SEV3, primary for SEV2
3. **Engineering lead**: SEV1 incidents, coordinates fix
4. **VP Engineering**: SEV1 with customer impact, external communication

### Incident Response Checklist

1. Acknowledge the alert
2. Determine severity
3. Open an incident channel
4. Assess blast radius
5. Mitigate (rollback, feature flag, scale up)
6. Root cause analysis (within 24h for SEV1/SEV2)
7. Write post-mortem
8. Track action items to closure
