# Shared tool system

The supported terminal and browser chat clients use the same tool registry and execution path:

`ConversationRuntime → ToolRegistry → local approval policy → system_tools → feedback to Gemini`

The registry validates Pydantic argument schemas before an approval prompt or execution. Synchronous handlers run in worker threads; subprocess tools use bounded output, timeouts and process-group cleanup.

## Registered tools

| Tool | Arguments | Risk / behaviour |
|---|---|---|
| `read_file` | `file_path` | Read-only; UTF-8 preview bounded by bytes and lines; binary files rejected |
| `list_dir` | `dir_path` | Read-only workspace listing |
| `write_file` | `file_path`, `content` | Local approval; atomic replacement; candidate Python syntax checked before write |
| `file_patch` | `file_path`, `search_text`, `replace_text` | Local approval; exact single replacement; target size bounded; Python syntax checked before write |
| `shell_exec` | `command` | Local approval; bounded execution/output; child environment excludes Gemini and dashboard credentials |
| `git_tool` | `command`, optional `message` | Local approval; argument parsing uses argv rather than shell interpolation |
| `code_search` | `pattern`, optional `path` | Workspace-scoped search |
| `doc_search` | `query` | Workspace documentation search |
| `request_clarification` | `question` | Ask the user for clarification |

`url_fetch` is intentionally disabled and is not registered. `update_scratchpad` is legacy schema source, not an active tool.

## Tool protocol

The model emits explicit tool fences. Simple arguments can use key-value lines:

```tool:read_file
file_path: README.md
```

Use JSON for multiline values, strings containing code fences, or unambiguous structured arguments:

```tool:write_file
{"file_path":"notes.txt","content":"first line\nsecond line"}
```

Ordinary Markdown code fences are not executable. Unknown tools fail closed. Tool output is bounded and returned to the same Gemini conversation for the next reasoning turn.

## Approval and trust boundaries

- Read-only tools do not prompt.
- File writes and patches display the target and a bounded diff before approval.
- Shell and Git operations require local terminal approval.
- Approval decisions and execution outcomes are written to the local audit log.
- The browser does not approve privileged operations itself; the backend terminal prompts the user.
- PRoot is not a security sandbox. An approved command has the permissions of the backend process.
- The direct browser tool endpoint is disabled by default and, when enabled, allows only `read_file` and `list_dir`.

The legacy DAG executor and agent orchestration are not part of the supported tool path. Do not add new tools to the retired executor; register them in the shared runtime with a schema and tests.
