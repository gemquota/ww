# Third-Party Dependency Audit — V6-C3#4

## Audit Process
Run quarterly to verify dependency health.

### Checks
1. **Licensing**: All deps have OSI-approved licenses
2. **Maintenance**: No unmaintained (>1yr) critical deps
3. **Security**: No known CVEs for used versions
4. **Vulnerability**: Run `pip-audit` or `safety check`

## Current Dependencies

| Package | Version | License | Health | Notes |
|---|---|---|---|---|
| fastapi | >=0.100 | MIT | Active | Web dashboard |
| pydantic | >=2.0 | MIT | Active | Schema validation |
| sqlite3 | stdlib | Public domain | Stable | Persistence |
| prompt-toolkit | >=3.0 | BSD | Active | TUI |
| httpx | >=0.25 | BSD | Active | HTTP client |
| colorama | >=0.4 | BSD | Active | Terminal colors |
| loguru | >=0.7 | MIT | Active | Logging |
| gemini-webapi | >=0.5 | MIT | Active | Gemini bridge |

## Automation
```bash
pip-audit --requirement requirements.txt --format json | jq '.vulnerabilities'
```
