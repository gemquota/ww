# FAQ & Troubleshooting

## Setup & Credentials

### Q: How do I get Gemini Web API credentials?
A: Visit https://gemini.google.com/ in a browser, open Developer Tools →
Application → Cookies, and copy `__Secure-1PSID` and
`__Secure-1PSIDTS`. Place them in `.env`:
```
SECURE_1PSID=your_value_here
SECURE_1PSIDTS=your_value_here
```

### Q: "SECURE_1PSID or SECURE_1PSIDTS not found in environment"
A: Ensure `.env` exists in the project root with valid credentials.
Run `python3 -c "from dotenv import load_dotenv; load_dotenv(); import os; print('OK' if os.getenv('SECURE_1PSID') else 'MISSING')"`
to verify.

### Q: The bridge starts but responds with "I need to set up my environment"
A: This typically means credentials are invalid or expired. Refresh them
by re-copying from the browser.

## Runtime

### Q: "Token limit exceeded" errors
A: The context window has filled up. Use `/compact` to summarize older
turns, or `/save` to persist the session and restart.

### Q: Tool calls are not being executed
A: Check that you're using the correct tool block format:
````
```tool:read
path: file.txt
```
````
Ensure dashes around the block are not present.

### Q: The bridge is hanging or not responding
A: Check your internet connection. The Gemini Web API requires internet
access. Press `Ctrl+C` to interrupt and type a new query.

### Q: How do I exit the bridge?
A: Type `exit`, `quit`, or press `Ctrl+C`. The bridge will
gracefully save state and close.

## File Operations

### Q: "Access denied. Path is outside workspace"
A: All file operations are sandboxed to the workspace root. You can
change the workspace in `config.yaml` (`workspace:` setting) or
via `WW_WORKSPACE` env var.

### Q: A SEARCH/REPLACE edit failed with "not found"
A: The fuzzy matcher requires the SEARCH block to match existing code
closely. Try:
1. Copy the exact text from the file
2. Ensure whitespace matches (tabs vs spaces)
3. Use `tool:write` for large changes instead

### Q: Can I undo a file change?
A: Yes — use `/undo`. Each undo restores the previous state of
modified files. History is bounded by `max_checkpoint_count`
(default: 20 checkpoints).

## Memory & Sessions

### Q: Does the bridge remember previous conversations?
A: Yes — it maintains 3-tier memory:
- **Tier A**: Recent verbatim turns (hot context)
- **Tier B**: Compressed facts from earlier turns
- **Tier C**: Summarized patterns (archival)

### Q: How do I save my session?
A: Use `/save my_session_name`. Load it later with
`/load my_session_name` or `python3 gemini_bridge.py --session my_session_name`.

### Q: Where is session data stored?
A: In the `.tel/` directory:
- `.tel/sessions/` — SQLite database with all interactions
- `.tel/telemetry.db` — aggregated telemetry
- `.tel/checkpoints/` — file state snapshots for `/undo`

## Dashboard

### Q: Dashboard won't start
A: Ensure you have `uvicorn` and `fastapi` installed:
```bash
pip install uvicorn fastapi
```
Then run:
```bash
python3 -c "import uvicorn; uvicorn.run('src.dashboard.app:app', host='0.0.0.0', port=8080)"
```

### Q: Dashboard shows "no sessions"
A: The dashboard reads from the telemetry database at `.tel/telemetry.db`.
Sessions only appear after running the bridge and making at least one query.

## Common Errors

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| `ImportError: No module named 'src'` | Wrong working directory | Run from project root |
| `gemini_webapi.exceptions.AuthError` | Expired credentials | Refresh `SECURE_1PSID`/`SECURE_1PSIDTS` |
| `sqlite3.OperationalError: database is locked` | Concurrent access | Only run one bridge instance |
| `Permission denied` | File outside workspace | Use `WW_WORKSPACE` to expand scope |
| `Coroutine 'write_file' was never awaited` | Tool call format error | Check tool block syntax |

## Credentials

### How do I know when my credentials expire?

Gemini Web API cookies (`__Secure-1PSID` and `__Secure-1PSIDTS`) typically last
several months but can expire silently. Symptoms of expired credentials:

- `AuthError` or `401 Unauthorized` in the logs
- Gemini returns empty responses or "access denied" messages
- The bridge starts but every query fails with a connection error

### How do I refresh expired credentials?

1. Open https://gemini.google.com in Chrome/Edge/Brave
2. Press F12 to open DevTools
3. Go to **Application → Cookies → gemini.google.com**
4. Find `__Secure-1PSID` and `__Secure-1PSIDTS`
5. Copy the new values and update your `.env` file:
   ```bash
   sed -i 's/SECURE_1PSID=.*/SECURE_1PSID=new_value/' .env
   sed -i 's/SECURE_1PSIDTS=.*/SECURE_1PSIDTS=new_value/' .env
   ```
6. Restart the bridge

### Can I automate credential rotation?

Not directly — the cookies are issued by Google's web authentication and cannot
be generated programmatically. However, you can:

- Set up a calendar reminder to check every 60 days
- Use the `--auth` flag to verify your current credentials:
  ```bash
  python gemini_bridge.py --auth
  ```
- Monitor logs for `AuthError` patterns with a watchdog script
