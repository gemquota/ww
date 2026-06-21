# Bridge API

## `gemini_bridge.py`

The main orchestrator module. Entry point for the WW Bridge application.

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `--script "query"` | One-shot mode: execute query, output JSON, exit |
| `--session <name>` | Load saved session on startup |
| `--verbose` | Enable verbose logging |

### Main Loop

```
main()
├── signal handlers (SIGINT/SIGTERM)
├── parse CLI arguments
├── load config (config.py → Settings)
├── initialize subsystems
│   ├── TelemetryManager
│   ├── MemoryManager
│   ├── AutoHealer
│   ├── PermissionManager
│   ├── CheckpointManager
│   ├── ConversationHistory
│   ├── WebGeminiClient
│   ├── ToolRegistry
│   └── PluginScanner
├── script mode → execute once, JSON output, exit
├── interactive mode → PromptSession loop
│   ├── Commands: /tokens, /undo, /compact, /reload, /verbose, /history, /memory, /save, /load, /sessions, /export
│   ├── User queries → safe_send_message()
│   │   └── AutoHealer on failure
│   └── Graceful shutdown on exit
└── end_session
```

### Key Functions

| Function | Purpose |
|----------|---------|
| `main()` | Application entry point |
| `initialize_bridge()` | Initialize Gemini client + chat session |
| `safe_send_message()` | Send message with retry + AutoHealer fallback |
| `shutdown_handler()` | Graceful SIGINT/SIGTERM handler |
| `get_bottom_toolbar()` | Dynamic TUI toolbar (token count, policy) |
