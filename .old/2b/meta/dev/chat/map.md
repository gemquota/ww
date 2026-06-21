Here’s the full system architecture map, laid out like a living circuit diagram where cognition flows through pipes, loops, and little animated gremlins of logic 🧠⚙️


---

🧭 GEMMA 2B HARNESS — FULL ARCHITECTURE MAP

┌──────────────────────────┐
                          │        USER INPUT        │
                          └────────────┬─────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │         CLI INTERFACE            │
                    │  (harness.py main loop)         │
                    └────────────┬─────────────────────┘
                                 │
                                 ▼
        ┌──────────────────────────────────────────────┐
        │            INTENT ROUTER LAYER              │
        │         (IntentRouter + Agent hints)        │
        └────────────┬─────────────────────────────────┘
                     │
                     ▼
     ┌───────────────────────────────────────────────┐
     │          TOOL FILTER / SCOPE SHAPER          │
     │   (restricts tools by detected intent)       │
     └────────────┬──────────────────────────────────┘
                  │
                  ▼
   ┌────────────────────────────────────────────────────┐
   │              SYSTEM PROMPT BUILDER                │
   │  - AGENTS.md / GEMINI.md / instructions          │
   │  - RepoMapper (structural memory snapshot)       │
   │  - Tool definitions (filtered subset)            │
   │  - Scratchpad summary                            │
   └────────────┬──────────────────────────────────────┘
                │
                ▼
   ┌────────────────────────────────────────────────────┐
   │        GEMMA 2B + OUTLINES DECODING CORE         │
   │  (structured ToolCall JSON FSM enforcement)      │
   └────────────┬──────────────────────────────────────┘
                │
        ┌───────┴───────────────────────────┐
        │                                   │
        ▼                                   ▼
┌──────────────────┐            ┌────────────────────────┐
│   THOUGHT STATE   │            │   FINAL ANSWER PATH    │
│ (reasoning trace) │            │ (assistant output)     │
└────────┬─────────┘            └────────────┬───────────┘
         │                                   │
         ▼                                   │
┌──────────────────────────┐                │
│     TOOL DECISION NODE    │                │
│  tool_name + tool_args    │                │
└────────────┬─────────────┘                │
             │                              │
             ▼                              │
   ┌───────────────────────────────┐        │
   │      TOOL REGISTRY LAYER      │        │
   │  (system_tools + custom tools)│        │
   └────────────┬──────────────────┘        │
                │                           │
                ▼                           │
     ┌──────────────────────────────┐       │
     │     TOOL EXECUTION ENGINE    │       │
     │  - file system ops           │       │
     │  - shell execution           │       │
     │  - git operations            │       │
     │  - scratchpad updates       │       │
     └────────────┬─────────────────┘       │
                  │                         │
                  ▼                         │
        ┌───────────────────────┐          │
        │     OBSERVATION        │          │
        │ (masked / compressed)  │          │
        └────────────┬──────────┘          │
                     │                     │
                     ▼                     │
        ┌──────────────────────────────┐   │
        │      MEMORY SYSTEM          │   │
        │  - conversation history     │   │
        │  - scratchpad state         │   │
        │  - masking layer            │   │
        └────────────┬───────────────┘   │
                     │                   │
                     └───────┬───────────┘
                             ▼
              (loops back into model context)


---

🧠 RUNTIME CONTROL PLANE (always running alongside)

┌───────────────────────┐
                    │   MASCOT CONTROLLER   │
                    └─────────┬─────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   THINKING STATE        SUCCESS STATE        CONFUSED STATE
   (⠶ / scan loops)      (✨ / alert joy)      (glitch / error)
        │                     │                     │
        └────────────┬────────┴────────────┬────────┘
                     ▼                     ▼
              TERMINAL RENDER THREAD (Mascot TUI)
                     │
          ┌────────────────────────────┐
          │  ASCII 7×9 BODY ENGINE     │
          │  - walking animation       │
          │  - eye state machine       │
          │  - position system         │
          └────────────────────────────┘


---

🧯 FAILURE & RECOVERY LAYER

TOOL FAILURE / LOOP EXHAUSTION
                      │
                      ▼
        ┌─────────────────────────────┐
        │     ESCALATION REPORT      │
        └────────────┬──────────────┘
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
┌───────────────────┐   ┌──────────────────────┐
│ LOCAL RETRY LOOP  │   │  GEMINI BRIDGE (OPT) │
│ (max 10 iterations)│   │  cloud diagnosis     │
└─────────┬─────────┘   └─────────┬────────────┘
          │                        │
          ▼                        ▼
   REACT RESTART        FIX STRATEGY INJECTION


---

🧩 SYSTEM CHARACTER (emergent identity)

┌────────────────────────────┐
             │   GEMMA 2B HARNESS AGENT   │
             └────────────┬───────────────┘
                          │
     ┌────────────────────┼────────────────────┐
     ▼                    ▼                    ▼
🧠 Cognition         🧰 Manipulation       🧿 Awareness
(LLM + Outlines)     (tools)              (memory + repo map)

     ▼                    ▼                    ▼
⚙️ Execution         📦 Environment       🎭 Expression
(ReAct loop)         (filesystem/git)     (mascot UI)


---

🌌 ONE-LINE ESSENCE

> A constrained 2B model wrapped in a structured reasoning engine, extended through tools, stabilized by memory compression, and emotionally projected into a terminal-dwelling animated organism.




---

If you want next-level evolution, I can:

turn this into a **real Mermaid diagram**

or design a **v2 architecture with parallel tool execution + cognitive graph memory**

or map how this behaves under load (context pressure collapse zones, etc.)


Just tell me which layer you want to push deeper into the machine.