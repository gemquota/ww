# Chunking and Worked Examples — V6-O1#3

## Chunking Strategy
Break complex topics into ~7±2 chunks:

### WW Bridge Architecture (5 chunks)
1. **Communicator Layer**: TUI/API entry, user interaction
2. **Overseer Layer**: Planning, delegation, orchestration
3. **Specialist Layer**: Tool execution, file operations
4. **Memory Layer**: Persistence, context management
5. **Security Layer**: Permissions, sandboxing

## Worked Example Format
```
PROBLEM: [Clear statement]
GOAL: [What success looks like]
STEP 1: [Action] → [Expected output]
STEP 2: [Action] → [Expected output]
...
VERIFICATION: [How to confirm]
```

## Example: Adding a Tool
```
PROBLEM: Register a new shell tool
GOAL: Call tool:shell_exec from agent
STEP 1: Define args schema → Pydantic model
STEP 2: Implement handler → Async function
STEP 3: Register in registry → registry.register()
STEP 4: Test with dry-run → tool:shell_exec ls -la
```
