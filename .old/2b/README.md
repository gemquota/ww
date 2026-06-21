# Gemma 2B Agent Harness

A standalone, local-first agent harness for the Gemma 2B model, designed for autonomous tool use, stateful memory management, and visual feedback.

## Features

- **Local-First Reasoning**: Powered by Gemma 2B via `llama-cpp-python` and `Outlines`.
- **Structured Output**: Uses Outlines for FSM-based JSON decoding to ensure tool call validity.
- **Multi-tier Memory**:
    - **Tier A (Hot)**: Verbatim recent history.
    - **Tier B (Compressed)**: Key facts and state changes.
    - **Tier C (Archival)**: Dense narrative summaries.
- **Persistent Cognitive Graph (PCG)**: Tracks causal relationships (`caused_by`, `result_of`) between thoughts, tools, and observations in SQLite.
- **Elastic Tooling**: Tool registry with lazy schema serialization and intent-based subsetting.
- **Autonomous Error Recovery**: 3-tier recovery loop (Retry -> Escalate -> Pause) with optional cloud-based 'Auto-Heal'.
- **Interactive TUI**: Includes a mascot animation system for affective UX.

## Installation

```bash
pip install -r requirements.txt
```

Ensure you have a Gemma 2B GGUF model file.

## Usage

```bash
# Start interactive session
python harness.py

# Run a specific task in YOLO mode
python harness.py -y "Check the status of the current git branch"

# Run benchmarks
python harness.py benchmark --run-all
```

## Directory Structure

- `core/`: Core agent, memory, and routing logic.
- `tools/`: Tool definitions and registry.
- `utils/`: Helpers for validation, repo mapping, and web clients.
- `gfx/`: Mascot and TUI assets.
- `docs/`: Detailed project documentation.
- `specs/`: Technical specifications and agent personas.
- `tests/`: Unit and integration tests.
- `dev/`: Research and development notes.

## Development Status

See `TASKS.md` and `DEVELOPMENT_PLAN.md` for current progress and future roadmap.
