# Module Cohesion — V7-06#4

## Principle
High cohesion, low coupling.

## Measurement
- `GodObjectDetector`: modules with >8 responsibilities
- `CouplingAnalyzer`: shared import patterns

## Targets
- Max 8 responsibility keywords per module
- Max 5 shared imports between module pairs
- Max 1 god object per release

## Enforcement
`src/v7/enforcement.py` — CI gates.