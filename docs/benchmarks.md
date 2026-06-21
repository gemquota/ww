# Benchmarks

## Overview

The benchmark suite evaluates system quality across 10 dimensions beyond simple pass/fail.

## Test Suite

| Category | Tests | Status |
|----------|-------|--------|
| Core Unit Tests | 20 | ✅ All pass |
| Tool Unit Tests | 22 | ✅ All pass |
| Integration Tests | 26 | ✅ All pass |
| Set 3 Tests | 17 | ✅ All pass |
| Quality (10-dim) | 47 | ✅ 46 pass, 1 known |

## Quality Dimensions

| # | Dimension | Description |
|---|-----------|-------------|
| 1 | Correctness | All tests pass on clean codebase |
| 2 | Latency / Performance | Component-level timing (context, token count, DAG) |
| 3 | Memory Efficiency | DB size, scratchpad growth under load |
| 4 | Error Recovery | Graceful handling of API failures, credential issues |
| 5 | Fuzz Testing | Random/corrupted inputs across all parsers |
| 6 | API Contract Conformance | Endpoints return correct schemas |
| 7 | Regression Sensitivity | Test count stability across results |
| 8 | Saturation Behavior | Behavior as context fills |
| 9 | Parallel Load | Concurrent session isolation |
| 10 | Cross-Session Isolation | Zero data leaks between sessions |

## Running Benchmarks

```bash
# Run all unit tests
python3 -m pytest tests/ -v

# Run quality benchmarks
python3 -m pytest tests/test_quality_10dim.py -v

# Full benchmark suite
python3 benchmarks/quality_bench.py

# DAG execution benchmarks
python3 benchmarks/dag_benchmarks.py
```

## Results

Results are archived in `benchmark_results/`:

| File | Description |
|------|-------------|
| `set1_results.md` | Core + Memory tests |
| `set2_results.md` | Tool + Integration tests |
| `set3_results.md` | DAG + Plugin tests |
| `set4_results.md` | Dashboard + Logging tests |
| `TBD.md` | Deferred tasks |
| `proposed_metrics.md` | Future benchmark proposals |
