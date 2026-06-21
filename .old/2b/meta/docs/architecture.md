# Architecture Overview

The Gemma 2B Agent Harness is built around a central execution loop that coordinates between several key components.

## Core Components

### 1. Agent Engine (`core/agent.py`)
Uses `Outlines` to wrap the `Llama` model. It provides methods for both text generation and structured JSON generation. It also handles the system instructions and formatting for the Gemma chat template.

### 2. Memory Manager (`core/memory.py`)
Manages the conversation state across three tiers:
- **Hot Context**: Recent messages kept verbatim.
- **Compressed Facts**: High-signal information extracted from history.
- **Archival Summary**: A lossy, dense summary of older events.
It also manages the **Persistent Cognitive Graph (PCG)** which stores events as nodes and causal relationships as edges in SQLite.

### 3. Intent Router (`core/router.py`)
Analyzes user input to identify the primary intent (e.g., RESEARCH, EDIT, GIT) and subsets the available tools to reduce token pressure and improve accuracy.

### 4. Tool Registry (`tools/registry.py`)
A centralized repository for tools. Supports:
- **Lazy Serialization**: Provides minimal summaries until a full schema is needed.
- **Tool Nodes**: Tools can define dependencies and tags.
- **DAG Resolution**: Can resolve tool execution orders for complex tasks.

## Causal Memory (PCG)

The PCG allows the agent to understand *why* certain actions were taken. By linking observations to the thoughts that caused them and final answers to the observations that supported them, the agent can perform more robust reasoning and error recovery.
