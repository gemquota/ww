# ADR-003: DAG-Based Tool Registry

**Status**: Accepted
**Date**: 2025-02-01

## Context

The bridge needs to provide tools to the LLM (shell execution, file I/O,
code search, URL fetching, etc.). These tools may have dependencies on
each other, and the system must validate that all dependencies are satisfied
before execution.

## Decision

Use a DAG (Directed Acyclic Graph) tool registry:

- Each tool is registered with its dependencies
- The registry validates no circular dependencies at registration time
- Tools are executed in topological order when dependencies exist
- Each tool has a Pydantic model for argument validation

```python
registry = ToolRegistry()
registry.register("read_file", read_file, "Read a file.", ReadFileArgs)
registry.register("write_file", write_file, "Write a file.", WriteFileArgs, depends_on=["read_file"])
```

## Consequences

**Positive**:
- Explicit dependency declaration
- Circular dependencies caught at registration
- Clear execution ordering
- Pydantic validation catches argument errors early

**Negative**:
- Slightly more complex tool registration
- Dependency resolution overhead for simple tools

## Alternatives Considered

1. **Flat tool list**: No dependency management
2. **Manual orchestration**: Caller must handle ordering
3. **Plugin-based**: More flexible but higher complexity
