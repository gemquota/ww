# 2B AGENT HARNESS (Standalone)

## Project Overview
This is an independent, local-first agent harness specifically optimized for **Gemma 2B** models. It provides a full CLI agent experience with autonomous tool use, persistent memory, and a "Self-Healing" loop via cloud-scale models.

## Core Features
- **Local Inference**: Powered by `llama-cpp-python` and `Outlines`.
- **Structural Reliability**: FSM-constrained decoding (JSON/ToolCall) with robust regex fallbacks.
- **Persistent State**: SQLite-based session database (`sessions.db`) tracking history and scratchpad.
- **Auto-Heal (wwfix)**: Automatic escalation of complex failures to Gemini Web for diagnosis.
- **Autonomous Tools**: File I/O, Shell execution, Git management, and tiered repo mapping.

## Setup & Execution
- **Install**: `pip install llama-cpp-python outlines pydantic`
- **Run (Interactive)**: `2b`
- **Run (YOLO Mode)**: `2b -y "task"`
- **Run (Autonomous)**: `2b -y -a "task"` (Enables Auto-Heal)

## Architecture
- `core/agent.py`: Outlines-based Gemma 2B model controller.
- `core/memory.py`: Context management (Summarization + Sliding Window) and SQLite DB.
- `tools/`: Registry for system and specialized tools.
- `utils/`: Repo mapping and instruction loading.

## Tool Protocols
- `read_file`, `write_file`, `shell_exec`, `git`, `update_scratchpad`.
- Automated retry logic (3 attempts) before `wwfix` escalation.
