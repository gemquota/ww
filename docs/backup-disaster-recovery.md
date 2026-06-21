# Backup & Disaster Recovery

**Last updated**: 2026-06-20
**Version**: 1.0.0

---

## Backup Strategy

| Data | Location | Backup Method | Frequency |
|------|----------|--------------|-----------|
| Session logs | `.tel/sessions/` | File copy | Real-time (WAL) |
| Telemetry | `.tel/telemetry.db` | SQLite dump | Daily |
| Checkpoints | `.tel/checkpoints/` | Git commit | On-demand |
| Profiles | `.tel/profiles/` | File copy | On-demand |
| Metrics | `.tel/metrics.db` | SQLite dump | Daily |

## Recovery Procedures

### Session Data Loss
1. Stop the bridge
2. Restore from `.tel/sessions/sessions.db` backup
3. Restart the bridge

### Corrupted Database
1. Run `DatabaseIntegrityChecker` to assess damage
2. Attempt WAL replay (`.tel/telemetry.db-wal`)
3. Fall back to latest checkpoint via `/undo`

### Full Workspace Recovery
```bash
# From git backup
git checkout <last-stable-commit>

# From file backup
tar -xzf .ww/backups/<timestamp>/workspace_full.tar.gz
```

## RPO/RTO Targets

| Tier | RPO (Recovery Point) | RTO (Recovery Time) |
|------|---------------------|---------------------|
| Session data | < 1 second (WAL) | < 30 seconds |
| Telemetry | < 1 hour | < 5 minutes |
| Full workspace | < 1 day | < 10 minutes |
