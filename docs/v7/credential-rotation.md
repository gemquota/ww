# Credential Rotation — V7-12#4

## Policy
API credentials rotated every 90 days minimum.

## Managed Credentials
- GEMINI_API_KEY (90 days)
- SECURE_1PSID (90 days)
- SECURE_1PSIDTS (90 days)

## Procedure
1. Generate new credentials
2. Update .env
3. Verify with debug_init
4. Run full test suite