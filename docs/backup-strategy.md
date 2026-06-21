# Backup & Disaster Recovery Strategy

Addresses NEW-V6-I3#2 (Ahmed Osman) — multi-environment strategy + backup.

## Backup Scope

| Data | Backup Method | Frequency | Retention |
|------|--------------|-----------|-----------|
| Session DB (`.ww/sessions/`) | SQLite dump + WAL checkpoint | Every 5 min | 7 days |
| Telemetry DB (`.tel/telemetry.db`) | SQLite dump | Every hour | 30 days |
| Checkpoints (`.tel/checkpoints/`) | rsync to backup dir | On creation | 20 versions |
| Configuration (`.env`, `config.yaml`) | Manual export | On change | Last 5 versions |
| Docker volumes | Volume snapshot | Daily | 7 days |

## Recovery Procedures

### Session DB Corruption
```bash
# Auto-detected on startup (PRAGMA integrity_check)
# Manual salvage:
python -c "
import sqlite3
conn = sqlite3.connect('.ww/sessions/sessions.db')
conn.execute('PRAGMA integrity_check')
"
# Restore from checkpoint:
./scripts/restore_from_checkpoint.py --latest
```

### Full Workspace Recovery
```bash
# From git (if used):
git checkout -- .
# From backups:
tar -xzf backups/ww-full-$(date +%Y%m%d).tar.gz -C /
```

## Verification

All backups are verified after creation:
- SQLite: `PRAGMA integrity_check` + row count comparison
- File: checksum comparison (SHA-256)
- Checkpoint: restore-to-temp verification

## RPO/RTO

| Tier | RPO | RTO |
|------|-----|-----|
| Session data | <5 min | <30s |
| Telemetry | <1 hour | <5 min |
| Full workspace | <24 hours | <1 hour |
