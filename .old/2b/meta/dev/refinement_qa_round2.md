# Refinement Q&A Round 2: Gemma 2B Agent Harness

Based on the RRP (Recursive Refinement Protocol) status and the need for further ambiguity reduction, here are the key architectural and behavioral questions for Round 2.

## 1. Context Priority & Injection
For the "Full CLI Agent" role, when the 2B model starts a task, what is the **minimal "high-signal" context** it must always have?
- **A) Local Scope Only**: Just the current file and immediate file tree.
- **B) Rule-Heavy**: The full `AGENTS.md` and `GEMINI.md` logic (higher token cost).
- **C) Structural Overview**: A dynamically generated "Repo Map" (summarized structure).

## 2. Multi-Agent Hand-off
How should the 2B harness interact with the main Gemini Bridge?
- **A) Stateless Worker**: Gemini Bridge spawns it for a single task, gets the result, and closes it.
- **B) Collaborative Peer**: The 2B agent can "talk back" to the main bridge to ask for more context or permission.
- **C) Autonomous Local Node**: It operates entirely independently with its own persistent SQLite session.

## 3. Error Recovery Strategy
If the 2B model fails to solve a task after its 10-iteration ReAct limit:
- **A) Escalate**: Automatically send the failure logs to the main Gemini Bridge (larger model) for a fix.
- **B) Checkpoint & Pause**: Save the session and wait for user intervention.
- **C) Recursive Retry**: Automatically summarize the failure and try one more time with a fresh context.

## 4. Tool Expansion
Beyond file and shell access, what is the **next "Power Tool"** we should build for the 2B agent?
- **A) Documentation Search**: Native support for searching library docs/APIs (Context7).
- **B) Code Symbol Search**: A specialized tool to grep for function definitions across the whole repo.
- **C) Git Manager**: Ability to create branches and commit changes locally.

---
**Please provide your preferences (e.g., "1C, 2B, 3A, 4B") to proceed with implementation.**
