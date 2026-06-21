# Refactoring Strategy — V7-03#4

## Principles
1. Small, reversible changes
2. Each refactor needs a test
3. Measure before/after with profiler
4. Document as ADRs

## Tools
- `TechDebtTracker` for tracking
- `FlameGraphProfiler` for measurement
- `@deprecated` for lifecycle

## Prioritization
Hot paths → God objects → Cyclic deps → Deprecated APIs