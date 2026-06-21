# Research Step 2: Optimization for Small LLMs (Gemma 2B)

## 1. Efficient Tool Use Patterns
- **Intent Routing:** Use a tiny classifier to narrow down the toolset to 3-5 relevant tools.
- **Symbolic Harnessing:** LLM for extraction, deterministic code for logic/execution.
- **Native Special Tokens:** Use `<|tool_call|>`, `<|tool_result|>`, `<|think|>`.
- **Observation Masking:** Replace verbose logs with summaries like `[Tool Output: 50 lines - Success]`.

## 2. Local Context Management
- **External State Management:** Maintain a "scratchpad" outside the prompt. Inject only the current state.
- **JIT Context:** Pull specific data slices rather than full files.
- **KV Cache Management:** Keep system prompts and tool definitions at the start.

## 3. Deployment & Sampling
- **Quantization:** Q4_K_M (under 1.5 GB RAM).
- **Sampling:** `temperature=0.0` for tool use; `temperature=1.0`, `top_p=0.95`, `top_k=64` for reasoning.
