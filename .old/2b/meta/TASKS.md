# Gemma 2B Agent Harness Development Tasks

- [ ] **Phase 1: Architecture & Scaffolding**
    - [x] Define project structure in `2b/` <!-- id: 0 -->
    - [x] Integrate `llama-cpp-python` and `Outlines` <!-- id: 1 -->
    - [x] Implement basic ReAct loop structure <!-- id: 2 -->

- [ ] **Phase 2: Context & Memory Management**
    - [x] Implement External State (Scratchpad) mechanism <!-- id: 3 -->
    - [x] Implement Observation Masking for tool outputs <!-- id: 4 -->
    - [x] Implement Hybrid Context (Summarization -> Sliding Window) <!-- id: 5 -->
    - [x] Implement Session Persistence (SQLite/JSON) <!-- id: 18 -->
    - [x] Implement Tiered Context (Rules + Repo Map + Local) <!-- id: 21 -->

- [ ] **Phase 3: Tool & Intent Management**
    - [x] Create tool registry and interface <!-- id: 6 -->
    - [x] Implement Elastic Tool Definitions (Minimalist vs Full) <!-- id: 19 -->
    - [x] Implement Intent Routing (Tiered Tooling) <!-- id: 7 -->
    - [x] Add example tools (file read, shell execute, search) <!-- id: 8 -->
    - [x] Add Git Manager Tool (branch, commit, status) <!-- id: 22 -->
    - [x] Add Doc Search Tool (Context7) <!-- id: 23 -->

- [ ] **Phase 4: Output Control & Validation**
    - [x] Migrate to Outlines-based FSM decoding <!-- id: 20 -->
    - [x] Implement JSON schema validation for tool calls <!-- id: 9 -->
    - [x] Implement 3-tier Error Recovery (Retry -> Escalate -> Pause) <!-- id: 24 -->
    - [x] Implement 'wwfix' autonomous cloud loop <!-- id: 25 -->

- [ ] **Phase 5: CLI & UX**
    - [x] Support interactive mode by default <!-- id: 11 -->
    - [x] Add colorama-based terminal styling <!-- id: 16 -->
    - [x] Implement /clear and /history CLI commands <!-- id: 17 -->


- [x] **Phase 6: Scaffolding Benchmarks** <!-- id: 13 -->
    - [x] **Memory Recall Suite**
        - [x] Implement runner for `memory_benchmarks.json`
        - [x] Measure precision/recall on 10+ facts.
        - [x] Validate summarization info-loss metrics.
    - [x] **Routing Accuracy Suite**
        - [x] Implement runner for `routing_benchmarks.json`
        - [x] Measure tool selection accuracy vs. "unnecessary tool" rates.
    - [x] **Recovery & Escalation Suite**
        - [x] Implement runner for `recovery_benchmarks.json`
        - [x] Measure success of "Auto-Heal" loop and bridge escalation.

- [x] **Phase 7: Final Audit** <!-- id: 14 -->
    - [x] Final project audit and documentation
