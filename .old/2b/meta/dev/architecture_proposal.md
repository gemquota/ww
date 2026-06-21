# Gemma 2B Agent Harness: Architectural Proposal & Strategy

## 1. Framework Choice: Outlines
**Outlines** is the chosen decoding engine for the 2B model.
- **Pros**: Guaranteed reliability via FSM decoding; prevents invalid JSON and conversational filler; saves context space by removing the need for "structured output" prompting.
- **Cons**: Higher setup complexity; requires logit access via backends like `llama-cpp-python`.
- **Decision**: Integrate Outlines to maximize model reliability and context efficiency.

## 2. Context Strategy: Hybrid Dual-Stage
A `ContextController` will manage the window:
- **Stage 1 (Aggressive Summarization)**: At 60% capacity, older turns are condensed into a high-density "State Log."
- **Stage 2 (Sliding Window)**: At 90% capacity, the oldest summaries/turns are dropped to maintain KV Cache efficiency.

## 3. Tool Schema: Elastic Definitions
Tools will support two modes:
- **Minimalist**: Name + 1-sentence description (for context-tight scenarios).
- **Full Schema**: Complete JSON Schema/Pydantic model (for high precision).
- **Automation**: The controller will toggle modes based on context pressure.

## 4. Agent Role: Full CLI Agent
The harness will handle:
- **File System Ops**: Read, write, search, delete.
- **Shell Control**: Execute commands with safety timeouts.
- **Self-Correction**: Automatic error-feedback loop for tool failures.

---

## Follow-up Questions for the User:

1. **Hardware/Execution Backend**: Outlines works best with `transformers`, `vLLM`, or `llama-cpp-python`. Since you have `llama.cpp` installed, would you prefer I use **llama-cpp-python** (enabling Outlines support via Python) or stick to the raw **llama-cli** (which would limit us to regex-based parsing instead of full Outlines integration)?

2. **Safety/Approval**: For a "Full CLI Agent," should I implement a **"YOLO" mode flag** (executing all tools automatically) or a **mandatory confirmation** for high-risk commands (like `rm` or `shell_exec`)?

3. **Persistence**: Should the agent maintain a **session database** (allowing you to resume conversations after closing the CLI) or should it be **stateless per-run**?
