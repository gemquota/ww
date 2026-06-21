# Gemma 2B Harness: Multi-Phase Development Plan

This plan tracks the evolution of the Gemma 2B Agent Harness into a stateful, causal, and visually expressive cognitive organism.
## 🟢 Phase 1: Foundation Refactoring & Observability
*Goal: Solidify the core loop, fix existing bugs, and enable event-driven visuals.*

- [x] **1.1 Mascot Lifecycle & Thread Safety** <!-- id: p1_1 -->
    - [x] Implement `shutdown()` and safe signal handling in `Mascot`.
    - [x] Move `Mascot` to an event-driven observer model (listener pattern).
- [x] **1.2 Tool Registry "Lazy" Serialization** <!-- id: p1_2 -->
    - [x] Implement `get_tool_summary()` (minimal) vs `get_tool_schema()` (full).
    - [x] Update loop to only inject full schemas during argument generation.
- [x] **1.3 Two-Stage Reasoning (Tool Shadow Mode)** <!-- id: p1_3 -->
    - [x] Refactor loop: Model selects tool name -> System injects schema -> Model fills args.
- [x] **1.4 Benchmark Runner Implementation** <!-- id: p1_4 -->
    - [x] Create `benchmarks/runner.py` to execute existing `.json` test suites.
    - [x] Report success rate, tokens, and steps.
## 🟡 Phase 2: Context Compression Engine (CCE)
*Goal: Token efficiency through event-driven memory and heuristic pruning.*

- [x] **2.1 Event Ingestion Layer** <!-- id: p2_1 -->
    - [x] Define `MemoryEvent` structure.
    - [x] Migrate `MemoryManager` to store events instead of raw strings.
- [x] **2.2 Importance Scorer** <!-- id: p2_2 -->
    - [x] Implement heuristic scoring (failures = high, noise = low).
- [x] **2.3 Multi-tier Memory Strata** <!-- id: p2_3 -->
    - [x] Tier A: Hot Context (verbatim).
    - [x] Tier B: Compressed Facts (JSON/Bullet points).
    - [x] Tier C: Archival Summary (lossy).
- [x] **2.4 Context Pressure Gauge** <!-- id: p2_4 -->
    - [x] Implement automatic pruning/summarization based on token usage.

## 🟠 Phase 3: Persistent Cognitive Graph (PCG)
...
---
*Progress: 45%*

- [x] **3.1 Graph Store Implementation** <!-- id: p3_1 -->
    - [x] Create `MemoryGraph` with Node/Edge storage (SQLite/JSON).
- [x] **3.2 PCG Integration** <!-- id: p3_2 -->
    - [x] Hook `_execute_task` to emit `caused_by` and `result_of` edges.
- [x] **3.3 Causal Retrieval** <!-- id: p3_3 -->
    - [x] Implement graph-aware context injection (retrieving nodes by causality).

## 🟢 Phase 4: Plugin DAG & Execution Kernel
*Goal: Tools as a composable topology instead of a flat list.*

- [x] **4.1 Tool Node Model** <!-- id: p4_1 -->
    - [x] Add dependencies, side-effects, and tags to `ToolNode`.
- [x] **4.2 DAG Resolution Engine** <!-- id: p4_2 -->
    - [x] Resolve execution orders for complex intents (e.g., RESEARCH -> [list, read, summarize]).
- [x] **4.3 Intent-to-Subgraph Mapping** <!-- id: p4_3 -->
    - [x] Update `IntentRouter` to return prioritized subgraphs.
- [x] **4.4 Parallel Execution** <!-- id: p4_4 -->
    - [x] (Optional/Advanced) Concurrent execution of independent branches.

## 🟢 Phase 5: Advanced Autonomy & UI Polish
*Goal: Collaborative reasoning, better recovery, and high-fidelity visuals.*

- [x] **5.1 Collaborative Peer Loop** <!-- id: p5_1 -->
    - [x] Implement `request_clarification()` tool for agent-user negotiation.
- [x] **5.2 Mascot Telemetry v2 (Affective UX)** <!-- id: p5_2 -->
    - [x] Map stress (retries), curiosity (search), and confusion (errors) to animations.
- [x] **5.3 Git Memory Spine** <!-- id: p5_3 -->
    - [x] Automated commits/diffs as a "reality audit" for the agent.
- [x] **5.4 Final Audit & Docs** <!-- id: p5_4 -->

---
*Progress: 100%*

