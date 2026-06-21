# ADR-005: Git-Based Checkpoint System

**Status**: Accepted
**Date**: 2025-02-15

## Context

The bridge modifies workspace files through tool execution. If the LLM
makes an error (wrong edit, file deletion, unwanted refactor), the user
needs a way to revert changes. Simple undo/redo buffers don't handle
the case where many files are modified across multiple tool calls.

## Decision

Use git as the checkpoint backend:

- Each checkpoint is a `git commit` with a structured message
- `/undo` performs `git reset --hard` to the previous checkpoint
- Checkpoints are created automatically before potentially destructive
  operations (write_file, file_patch, shell_exec with write commands)
- Users can also create manual checkpoints

```python
class CheckpointManager:
    def create_checkpoint(self, label: str) -> Optional[str]:
        # git add -A && git commit -m "[WW] checkpoint: {label}"
        ...
    def undo(self) -> bool:
        # git reset --hard HEAD~1
        ...
```

## Consequences

**Positive**:
- Leverages battle-tested git for versioning
- Full file-level granularity
- Checkpoints are visible in `git log`
- No separate storage backend needed

**Negative**:
- Requires git to be installed and the workspace to be a git repo
- Checkpoint commits pollute git history
- Large checkpoints can be slow (full git add -A)
- History rewriting (rebase) can break checkpoint ordering
