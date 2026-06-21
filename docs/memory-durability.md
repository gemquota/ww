# Memory & Storage Durability

Addresses NEW-D1#1 (Dr. Helena Bergström).

## Data Stores

| Store | Purpose | Engine | Durability |
|-------|---------|--------|------------|
| Session DB | Conversation history, tool calls | SQLite (WAL) | fsync every 5s |
| Telemetry DB | Usage metrics, activation funnel | SQLite (WAL) | Best-effort fsync |
| Checkpoint store | File snapshots for undo | Filesystem + JSON | Atomic writes |
| Prompt log | Prompt/response pairs | JSONL (append) | Per-write fsync |

## Durability Guarantees

### Session Data
- **Write strategy**: WAL mode + `PRAGMA synchronous=NORMAL`
- **Recovery point**: At most 5 seconds of data loss on crash
- **Verification**: `PRAGMA integrity_check` on startup

### Checkpoints
- **Write strategy**: Atomic directory creation + JSON history update
- **Recovery**: Partial checkpoints are detected and cleaned on startup
- **Retention**: Last 20 checkpoints kept, oldest pruned automatically

## WAL Checkpoint Strategy

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA wal_autocheckpoint=1000;
```

- WAL mode enables concurrent reads during writes
- Checkpoint every 1000 pages (~4MB)
- Busy timeout of 5s prevents SQLITE_BUSY errors

## Crash Recovery

On startup, the system:

1. Runs `PRAGMA integrity_check` on all SQLite databases
2. Detects interrupted checkpoint operations
3. Attempts auto-repair for corruption (WAL checkpoint rollback)
4. Logs recovery outcome to telemetry

## RPO/RTO Targets

| Data | RPO (Recovery Point Objective) | RTO (Recovery Time Objective) |
|------|-------------------------------|-------------------------------|
| Session | <5s | <30s |
| Telemetry | <1min | <60s |
| Checkpoints | Zero (atomic writes) | <10s |
