# Secret Management — V6-I1#3

## Principles
- No secrets in code, config, or documentation
- Secrets loaded from environment variables
- Secret rotation supported without code changes

## Current Secrets

| Secret | Env Variable | Used By |
|---|---|---|
| Gemini API Key | GEMINI_API_KEY | WebGeminiClient |
| Cookie 1PSID | SECURE_1PSID | WebGeminiClient |
| Cookie 1PSIDTS | SECURE_1PSIDTS | WebGeminiClient |
| Dashboard API Key | WW_DASHBOARD_API_KEY | Dashboard auth |

## Best Practices
- Use `.env` file locally (gitignored)
- Use GitHub Secrets in CI
- Rotate keys every 90 days
- Never log secret values (mask in output)
- Audit secret usage quarterly
