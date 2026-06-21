# Secret Management

**Last updated**: 2026-06-20
**Version**: 1.0.0

---

## Credential Sources

WW Bridge supports these credential sources, in priority order:

1. **Environment variables** (`.env` file or system env)
2. **Config file** (`config.yaml` credentials section)
3. **CLI arguments** (`--auth` flag)

## Best Practices

- Never commit `.env` files (they're in `.gitignore`)
- Use `GEMINI_API_KEY` for API key authentication
- Use `SECURE_1PSID` + `SECURE_1PSIDTS` for cookie auth
- Rotate credentials regularly
- Use different credentials for development vs production

## Security Notes

- Credentials are loaded at startup and held in memory
- The dashboard API uses API key authentication via `X-API-Key` header
- Plugin permissions are sandboxed — plugins cannot access credentials directly
- All credential access goes through `src/config.py:get_env()` (centralized)
