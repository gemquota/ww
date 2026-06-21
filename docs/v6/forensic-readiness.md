# Forensic Readiness — V6-S1#4

## Principles
- All agent actions are logged and traceable
- Tamper-evident log chain protects integrity
- Logs preserved for incident investigation

## Log Chain Architecture
- Merkle tree of log entries (SHA-256)
- Each entry references previous entry hash
- Integrity verified on startup

## Documentation Requirements
- Log retention policy: 90 days minimum
- Logs stored in `.tel/` directory
- Export format: JSONL with timestamps
- Investigation playbook in docs/runbook.md

## Key Questions
1. What did the agent do? → Log chain
2. Why did it do it? → Decision trace
3. When did it happen? → Timestamp chain
4. Who requested it? → Session ID + API key
