# Commands Reference

WW Bridge supports the following slash-commands in interactive mode.

| Command | Description |
|---------|-------------|
| `/tokens` | Show current token utilization (e.g., `45% of 128K`) |
| `/undo` | Undo the last file change (restores from checkpoint) |
| `/compact` | Force context compaction (summarizes older turns) |
| `/reload` | Reload config and reinitialize subsystems |
| `/verbose` | Toggle verbose mode (shows raw LLM responses) |
| `/history` | Show checkpoint history with descriptions |
| `/memory` | Show scratchpad summary from memory system |
| `/save <name>` | Save current session to a named checkpoint |
| `/load <name>` | Load a previously saved session |
| `/sessions` | List all saved sessions |
| `/export` | Export telemetry data as Markdown report |

## Command Details

### `/tokens`
Displays a bar chart of current token usage across context tiers:
```
Tokens: [████████░░░░░░░░░░░░] 45% of 128K
System: 2.1K | History: 38.4K | Context: 16.2K
```

### `/undo`
Restores files modified by the last tool call. Uses git-patch reverse
application + file backup restoration. Each undo pops one checkpoint.
Undo history is bounded by `memory.max_checkpoint_count` (default: 20).

### `/compact`
Triggers rule-based context compaction: older conversation turns are
summarized into compressed tier-b facts. This frees token budget in
the context window. Compaction preserves recent turns and key results.

### `/save <name>` and `/load <name>`
Sessions persist to the configured telemetry database. A saved session
includes conversation history, memory scratchpad, and checkpoint index.
Use `/sessions` to list available named sessions.

### `/export`
Generates a structured Markdown report of all interactions in the
current session, including tool calls, results, and timing information.
