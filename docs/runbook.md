# WW Bridge — Operations Runbook

**Purpose**: Documented procedures for common operational scenarios.
**Audience**: Operators, maintainers, and advanced users.

---

## 1. Crash Recovery

**Symptoms**: Bridge process exits unexpectedly; session interrupted.

**Steps**:
1. Check `.logs/sessions/` for the most recent session log
2. Restart the bridge: `python gemini_bridge.py`
3. Use `/sessions list` to find interrupted sessions
4. Use `/sessions load <id>` to restore session state
5. Check `~/.ww/` for checkpoint data

**Prevention**:
- The bridge auto-saves state every 5 seconds
- Checkpoints are created before destructive operations
- Use `/undo` to roll back to last checkpoint

---

## 2. Gemini API Outage

**Symptoms**: "Gemini Web API not available", "Connection Error", or timeout errors.

**Steps**:
1. Check [Gemini API Status](https://status.gemini.google.com/)
2. Verify credentials:
   - `python gemini_bridge.py --health`
   - Check `SECURE_1PSID` and `SECURE_1PSIDTS` in `.env`
3. If using API key: verify `GEMINI_API_KEY` is set and has quota
4. Retry after 30 seconds — the circuit breaker will auto-recover
5. If persistent: try `--use-api` flag to switch auth methods

**Escalation**:
- If outage > 1 hour: post in project discussions
- Document incident in a post-mortem

---

## 3. SQLite Corruption

**Symptoms**: "database disk image is malformed", "SQL logic error", or checkpoint failures.

**Steps**:
1. Stop the bridge immediately
2. Backup the corrupted database: `cp .logs/telemetry.db .logs/telemetry.db.corrupt`
3. Run integrity check: `sqlite3 .logs/telemetry.db "PRAGMA integrity_check;"`
4. If corrupted, restore from last good backup
5. Use `/salvage` to extract intact records (if implemented)

**Prevention**:
- WAL mode reduces corruption risk
- Regular `PRAGMA integrity_check` on startup
- Back up before major upgrades

---

## 4. Session Salvage

**Symptoms**: Session fails to load; conversation history missing.

**Steps**:
1. Identify the session ID from `.logs/sessions/`
2. Attempt `/sessions list` to find salvageable sessions
3. If database is intact but session corrupted, try `/export --share` to extract data

---

## 5. Disk Full

**Symptoms**: Checkpoint fails; telemetry write errors; bridge becomes unresponsive.

**Steps**:
1. Check disk: `df -h`
2. Clean old logs: `rm -rf .logs/sessions/old/`
3. Clean old checkpoints: `rm -rf .ww/checkpoints/`
4. Compact databases: `sqlite3 .logs/telemetry.db "VACUUM;"`
5. Restart bridge

---

## Escalation Paths

| Severity | Response Time | Notify |
|----------|---------------|--------|
| CRITICAL (bridge down) | 15 min | Project maintainers |
| HIGH (features broken) | 1 hour | Issue tracker |
| MEDIUM (degraded) | 4 hours | Documentation |
| LOW (cosmetic) | Next release | Comment on issue |
