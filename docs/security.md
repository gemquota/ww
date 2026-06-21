# Security Model

## Overview

WW Bridge implements a defense-in-depth security architecture with three layers:
sandboxing, approval policies, and audit logging.

## Layer 1: Workspace Sandbox

All file operations are confined to the workspace root directory.

### Path Traversal Prevention
- `Sandbox.is_safe_path()` resolves both the requested path and the workspace
  root, then verifies the requested path is a prefix match
- Applied to: `read_file`, `write_file`, `list_dir`, `file_patch`, `code_search`
- Prevents: `../../../etc/passwd`, symlink escapes, UNC path injections

### Protected Paths
The following paths are **always blocked** from reads and writes:
- `.env` — credentials file
- `.git/` — git internals
- `.ww/`, `.tel/` — bridge internal state

## Layer 2: Approval Policies

Three policies control shell command execution:

| Policy | Behavior |
|--------|----------|
| `always` | All commands auto-approved (fast, risky) |
| `on-request` | Dangerous/unknown commands prompt for confirmation |
| `never` | All shell commands auto-allowed (only safe commands) |

### Command Classification

Commands are classified into three risk levels:

| Level | Examples | Behavior |
|-------|----------|----------|
| **SAFE** | `ls`, `cat`, `pwd`, `git status`, `pip list` | Auto-allowed |
| **MUTATING** | `touch`, `mkdir`, `git add`, `pip install` | Allowed, tracked |
| **DANGEROUS** | `rm -rf`, `sudo`, `> /dev/sda`, `chmod 777` | Requires approval |

### Approval Prompt

When a dangerous command is detected:
```
  ⚠️ Request Approval: rm -rf /data (y/n):
```
Type `y` to allow once, `n` to deny.

## Layer 3: Audit Logging

Every operation is logged to the telemetry database:
- All tool calls with arguments
- Shell commands executed (redacted)
- File reads, writes, and patches
- Permission approvals and denials
- Session start/end timestamps

## Configuration

Set the policy in `config.yaml`:
```yaml
policy: "on-request"  # always | on-request | never
```

Or via environment:
```bash
export WW_POLICY=on-request
```

## Best Practices

1. **Production**: Use `on-request` policy — balances security with usability
2. **CI/CD**: Use `always` or `never` policy — non-interactive environments
3. **Multi-tenant**: Run each workspace in its own container (see deploy/)
4. **Credentials**: Never commit `.env` — it's in `.gitignore` by default
5. **Audit**: Review telemetry regularly to detect anomalous tool usage
