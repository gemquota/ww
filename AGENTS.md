# AGENTS.md

## Project Overview
WW (Gemini Multi-Agent Bridge) is a Python-based CLI harness that provides an agentic coding loop powered by Google Gemini. It implements a 3-tier agent hierarchy (Communicator → Overseer → Specialists) with tool execution, workspace sandboxing, and context management.

## Setup Commands
- Install dependencies: `pip install -r requirements.txt`
- Run the bridge: `python gemini_bridge.py`
- Run with verbose mode: `python gemini_bridge.py --verbose`
- Run syntax check: `python -m py_compile gemini_bridge.py`

## Architecture
- **3-Tier Agency**: Communicator (UI/Entry) → Overseer (Technical Lead) → Specialized Agents (Execution)
- **Bridge**: Python asyncio terminal with direct filesystem access via tool blocks
- **Context**: Smart workspace ingestion with .gitignore awareness and repo mapping
- **Permissions**: Granular approval system for shell commands and file writes
- **Checkpoints**: Automatic git-based state snapshots with /undo support

## Code Style
- Python 3.10+ with asyncio patterns
- Use type hints for all function signatures
- Prefer `pathlib.Path` over `os.path` for file operations
- Use structured tool blocks (`tool:xxx`) for all system interaction
- Prefer surgical edits via `tool:replace` over full file rewrites

## Testing Instructions
- Syntax check: `python -m py_compile *.py`
- Verify sandboxing: attempt to read `/etc/passwd` (should be blocked)
- Verify fuzzy matching: test `tool:replace` with slightly mismatched whitespace

## Security Considerations
- NEVER read `.env` files or expose credentials
- All file operations are sandboxed to WORKSPACE_ROOT
- Shell commands require approval for unknown/dangerous operations
- Path traversal attacks are blocked by the Sandbox class
