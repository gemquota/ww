# Tool System

## Overview

The ToolRegistry manages all available tools with Pydantic-schematized arguments and DAG dependency resolution.

## Available Tools

| Tool | Description | Args Schema |
|------|-------------|-------------|
| `read_file` | Read file contents | `ReadFileArgs(path)` |
| `list_dir` | List directory contents | `ListDirArgs(path)` |
| `write_file` | Write content to file | `WriteFileArgs(path, content)` |
| `shell_exec` | Execute shell command | `ShellExecArgs(command, cwd, timeout)` |
| `git_tool` | Git operations | `GitArgs(action, args)` |
| `doc_search` | Search documentation | `DocSearchArgs(query)` |
| `code_search` | Search code across project | `CodeSearchArgs(pattern, path)` |
| `file_patch` | Surgical line edits | `FilePatchArgs(path, operations)` |
| `url_fetch` | HTTP GET request | `UrlFetchArgs(url, timeout)` |
| `update_scratchpad` | Update memory scratchpad | `UpdateScratchpadArgs(key, value)` |
| `request_clarification` | Ask user for clarification | `ClarificationArgs(question)` |

## Usage Examples

### Read a file
```tool:read
path: src/config.py
```

### Write a file
```tool:write
path: output.txt
content: Hello, World!
```

### SEARCH/REPLACE edit
```tool:replace
path: src/config.py
find: timeout: 45
replace: timeout: 60
```

### Execute shell command
```tool:shell
command: pytest .tests/ -q
timeout: 30
```

### Search codebase
```tool:search
pattern: def get_settings
path: src/
```

### Fetch URL
```tool:fetch
url: https://api.example.com/data
timeout: 10
```

---

## DAG Execution

Tools can declare dependencies. The ToolRegistry resolves the execution order and can execute
independent branches in parallel.

```python
registry = ToolRegistry()
registry.register(read_file, deps=[])
registry.register(code_search, deps=[])
registry.register(file_patch, deps=["read_file"])  # depends on read_file

# Resolve execution order
order = registry.resolve_dag(["file_patch", "code_search"])
# Result: [code_search, read_file, file_patch]
```

## Tool Tags

Each tool can be tagged for intent-based subsetting:

- `file_operation` — read_file, write_file, list_dir, file_patch
- `search` — doc_search, code_search
- `communication` — request_clarification
- `execution` — shell_exec
- `network` — url_fetch
- `memory` — update_scratchpad
