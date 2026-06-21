# Scalability Architecture

Addresses NEW-B2#4 (Dr. Aisha Bakari).

## Current Architecture

The WW Bridge is designed as a **single-node agentic coding harness**.
This document describes the current scalability characteristics and
the architectural decisions that enable future scaling.

## Single-Node Throughput

| Resource | Current Limit | Bottleneck |
|----------|--------------|------------|
| Concurrent sessions | 1 (blocking REPL) | Python GIL + synchronous tool dispatch |
| Tool dispatch | Sequential (parallel for independent tools) | DAG dependency resolution |
| Memory (SQLite) | Single connection | WAL mode + connection pooling |
| Token counting | Inline synchronous | Workspace context assembly |

## Identified Constraints

1. **Single Runtime** — All components run in one process. Scaling to
   multiple concurrent users requires process-level isolation.

2. **Synchronous REPL Loop** — The main loop is a sequential
   read-think-execute cycle. This is inherent to the agent use case.

3. **SQLite Single-Writer** — WAL mode enables concurrent reads but
   writes are still serialized.

4. **Gemini API Rate Limits** — The primary external constraint.
   Current approach: exponential backoff + circuit breaker.

## Parallel Tool Dispatch

Independent tools (no DAG dependency) are dispatched using
`asyncio.gather()`. DAG-dependent tools remain sequential.

```
[Tool Request]
       |
   [DAG Resolver]
       |
   +---+---+
   |       |
  T1(A)  T2(A)   <- independent, parallel
   |       |
   +---+---+
       |
      T3(B)      <- depends on T1+T2, sequential
```

## Memory Scaling

The 3-tier memory system (Hot/Facts/Summary) uses LRU eviction
to bound memory growth per session.

| Tier | Size Limit | Persistence |
|------|-----------|-------------|
| Hot | 5 entries | In-memory + SQLite |
| Facts | 20 entries | SQLite |
| Summary | 30 entries | SQLite |

## Future Scaling Paths

1. **Process-per-session**: Each user session runs in a separate
   container. Communication via Redis pub/sub.

2. **Read replicas**: SQLite read replicas for dashboard/analytics.

3. **Sharded memory**: Partition sessions across multiple SQLite
   databases by session ID hash.

4. **Async API server**: Flask/FastAPI frontend decouples HTTP
   from agent execution.
