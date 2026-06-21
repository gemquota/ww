# Chaos Engineering Framework

## Purpose
Systematic fault injection and recovery validation for WW Bridge. The chaos framework ensures the system can survive real-world failures including API outages, SQLite corruption, disk-full conditions, and plugin crashes.

## Experiment Catalog

| Experiment | Description | Frequency | Status |
|-----------|-------------|-----------|--------|
| API Outage | Simulate Gemini API unavailability | Weekly | Planned |
| SQLite Corruption | Inject corrupted WAL/journal files | Bi-weekly | Planned |
| Disk Full | Simulate ENOSPC during checkpoint writes | Monthly | Planned |
| Plugin Crash | Force plugin panic during tool dispatch | Weekly | Planned |
| Network Partition | Delay/drop tool executor network calls | Monthly | Planned |

## Running Experiments
```bash
python -m pytest chaos/ -v
```

## Principles
1. Experiments must have automated rollback
2. No experiment should affect production data
3. Each experiment documents blast radius and recovery procedure
4. Post-experiment: update runbook if new failure mode discovered
