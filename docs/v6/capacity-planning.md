# Capacity Planning — V6-I2#4

## Current Constraints
- Single-node architecture
- SQLite storage (concurrent write limit)
- Gemini API rate limits (~60 req/min for free tier)
- Memory: context window token limits

## Scaling Dimensions

| Dimension | Current Limit | Bottleneck | Upgrade Path |
|---|---|---|---|
| Concurrent users | 1 (CLI) | Single process | Multi-process |
| Storage | Unlimited | Disk space | Sharding |
| API calls | 60/min | Gemini quota | Multiple keys |
| Context | 1M tokens | Window | Compaction |

## Monitoring
- Track: API call count, memory usage, DB size
- Alert at: 80% of any limit
- Review: Monthly capacity review
