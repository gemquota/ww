# Memory System

## 3-Tier Context

| Tier | Name | Description | Persistence |
|------|------|-------------|-------------|
| A | **Hot Context** | Recent verbatim conversation turns | In-memory |
| B | **Facts / Scratchpad** | Compressed key-value facts from earlier turns | SQLite |
| C | **Archival Summary** | Periodically generated summaries of long-term patterns | SQLite |

## PCG (Procedural Causal Graph)

A lightweight causal graph that tracks cause-effect chains across conversation turns.

### Schema

```python
class CausalNode(BaseModel):
    node_id: str
    turn_index: int
    event_type: str  # "tool_call", "error", "decision", "observation"
    content: str
    cause_ids: list[str] = []  # IDs of nodes that caused this
    effect_ids: list[str] = [] # IDs of nodes this caused
```

### Operations

- `add_causal_edge(source_id, target_id)`
- `get_causal_chain(event_id)` — returns full chain from root cause to final effect
- `build_context()` — injects PCG chains into system prompt
