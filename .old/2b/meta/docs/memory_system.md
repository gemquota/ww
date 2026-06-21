# Memory & PCG System

The memory system is designed to handle long-running sessions by gracefully compressing old information while maintaining causal links.

## Multi-tier Strata

The `ContextController` monitors token pressure. When it exceeds a threshold (70% of max context), it moves older turns into Tier B and C.

- **Tier B (Facts)**: Extracted JSON/Bullet points that represent the "state of the world".
- **Tier C (Archive)**: A dense narrative that provides context for the facts.

## Graph Structure

The PCG uses two main edge types:
- `caused_by`: Links a thought to the user input or observation that triggered it.
- `result_of`: Links a tool observation or final answer to the thought/tool call that produced it.

This graph is persisted in SQLite, allowing for cross-session causal retrieval in future iterations.
