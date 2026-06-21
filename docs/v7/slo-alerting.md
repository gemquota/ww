# SLO Alerting — V7-07#2

## Defined SLOs
| Indicator | Target | Window |
|-----------|--------|--------|
| API success rate | ≥ 99% | 30 days |
| P99 latency | ≤ 5s | 7 days |
| Test pass rate | ≥ 98% | 14 days |

## Channels
CI notifications + DORA metrics dashboard.

## Implementation
`.tel/scripts/dora_dashboard.py`