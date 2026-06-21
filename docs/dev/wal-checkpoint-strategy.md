# WAL Checkpoint Strategy — NEW-V5-D1#2

## Overview
SQLite WAL (Write-Ahead Log) mode enables concurrent reads during writes, improving performance and reducing lock contention. This document defines the checkpoint strategy.

## Current Configuration
All SQLite databases use:
- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=NORMAL`
- `PRAGMA busy_timeout=5000`

## Databases
| Database | Path | WAL Auto-checkpoint | fsync Strategy |
|----------|------|--------------------|----------------|
| Session DB | `.ww/sessions/sessions.db` | 1000 pages | Every 5s via `periodic_flush` |
| Telemetry DB | `.ww/telemetry/telemetry.db` | 1000 pages | Best-effort on write |
| Events DB | `events.db` | 1000 pages | On explicit commit |

## Checkpoint Trigger Conditions
1. **Periodic**: Every 1000 WAL pages (auto-checkpoint)
2. **On shutdown**: Explicit `PRAGMA wal_checkpoint(TRUNCATE)` during graceful shutdown
3. **On explicit checkpoint**: `CheckpointManager.full_checkpoint()` for user-initiated snapshots
4. **On crash recovery**: At startup, WAL is automatically replayed

## Verification
```python
import sqlite3
conn = sqlite3.connect(".ww/sessions/sessions.db")
mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
assert mode == "wal"
```
