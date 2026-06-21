# Troubleshooting Guide

Common issues with WW Bridge and their resolutions.

---

## 1. "No credentials found" on startup

**Symptom**: Bridge exits with "No credentials found. Run with --auth".

**Likely causes:**

| Cause | Check | Fix |
|-------|-------|-----|
| `.env` file missing | `ls -la .env` | Create `.env` in project root |
| Wrong env var name | `grep GEMINI_API_KEY .env` | Use `GEMINI_API_KEY=xxx` or `SECURE_1PSID=xxx` |
| Extra whitespace/quotes | `cat .env \| xxd \| head` | Remove `"`, `'`, or trailing spaces |
| Expired cookie | Re-extract from browser | Run `python gemini_bridge.py --auth` |
| File not loaded | Add `print(os.getenv('GEMINI_API_KEY'))` after `load_dotenv()` | Check `.env` is in root and properly formatted |

**Quick fix**: Run `python gemini_bridge.py --auth` for setup instructions.

---

## 2. Gemini API returns "Resource has been exhausted"

**Symptom**: Bridge shows rate limit errors after a few queries.

**Cause**: Gemini free tier has ~10 requests per minute limit.

**Resolution**: Wait 30-60 seconds and retry. The bridge has built-in rate
limiting (configurable via `WW_GEMINI__RATE_LIMIT_RPM` or `gemini.rate_limit_rpm`
in `config.yaml`). Reduce the limit if you're hitting it frequently.

---

## 3. SQLite "database is locked" errors

**Symptom**: Crash with `sqlite3.OperationalError: database is locked`.

**Cause**: Multiple processes accessing the same `.ww/sessions/sessions.db` file.

**Resolution**: 
- Only run one bridge instance at a time
- If the lock persists, delete the WAL files: `rm -f .ww/sessions/sessions.db-wal .ww/sessions/sessions.db-shm`
- The bridge now uses WAL mode with busy_timeout=5000ms to reduce this

---

## 4. Tool output is truncated

**Symptom**: Response ends with "[... truncated ...]".

**Cause**: Tool outputs are limited to 5000 characters by default.

**Resolution**: 
- For file reads, the truncation is intentional to avoid overflowing the context window
- For shell commands, pipe to `head -100` to limit output yourself
- The truncation is applied per-tool, not to the overall conversation

---

## 5. Plugins not loading

**Symptom**: `/plugins` shows "None."

**Causes**:

| Cause | Check | Fix |
|-------|-------|-----|
| No plugins directory | `ls plugins/` | Create `plugins/` directory |
| Plugin not in right format | Check for `plugin.json` | Follow plugin API docs |
| Import error | Run `python -c "from plugins.xxx import *"` | Fix import errors in plugin code |
| Plugin scanning disabled | Check `config.yaml: plugins.auto_load` | Set `auto_load: true` |

---

## 6. Very slow first response

**Symptom**: First query takes 15-30 seconds before any response.

**Cause**: The bridge loads agent definitions, memory state, and workspace
context on first query. Subsequent queries are faster due to caching.

**Resolution**: Normal behavior. Use `--verbose` to see what's loading.

---

## 7. "Invalid file descriptor: -1" warning in tests

**Symptom**: Warning appears during test runs but tests pass.

**Cause**: The crash-safe fsync function attempts to open the SQLite database
file for fsync, which is sometimes not available in sandboxed test environments.

**Resolution**: Cosmetic warning only. Can be safely ignored.

---

## 8. Workspace files not visible to the bridge

**Symptom**: Tools can't find files that exist on disk.

**Cause**: The workspace root is set at startup and all file operations are
sandboxed relative to that root. If you moved the project, files may be
outside the sandbox.

**Resolution**: Check `config.yaml` workspace setting, or restart the bridge
from the correct directory.

---

## 9. `/undo` doesn't restore files

**Symptom**: Checkpoint undo completes but files are unchanged.

**Causes**:

| Cause | Fix |
|-------|-----|
| No checkpoints exist yet | Perform at least one file write first |
| Git not available | Install git (`apt install git` or `pkg install git`) |
| Workspace is not a git repo | Run `git init` in the project root |
| Uncommitted changes in the way | Run `git stash` before undo |

---

## 10. "Command not found" in shell_exec

**Symptom**: Tool returns "ERROR: [Errno 2] No such file or directory".

**Cause**: The shell tool uses `asyncio.create_subprocess_shell()` which
runs through `/bin/sh`. If a command exists in your interactive shell but
not in `/bin/sh` (e.g., aliases, bash-specific syntax), it won't work.

**Resolution**: Use full paths to commands. For complex shell scripts,
write them to a file first with `write_file`, then execute the file.

---

## Still stuck?

Open a GitHub issue with:
1. The exact command you ran
2. The full error output (use `--verbose` for detailed logs)
3. Your OS and Python version (`python --version`)
4. Any relevant `.env` or `config.yaml` settings (redact secrets)
