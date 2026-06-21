# Mascot — Terminal Agent Status Indicator

The mascot is a real-time ANSI-rendered status indicator that lives in the bottom-right corner of the terminal during a WW bridge session. It visually reflects the agent's internal state through facial expressions, body animation, and movement patterns — no log reading required.

---

## State Machine

The mascot runs an autonomous update loop at ~6.6 FPS (0.15s interval) with 9 states:

```
                    ┌──────────────────────────────┐
                    │           SLEEP              │
                    │  (20 frames = ~3s startup)   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │          WAKING               │
                    │  (10 frames = ~1.5s)          │
                    │  eye: "." → " ░ "             │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────┴───────────────┐
                    │          WAITING              │◄──────────────────────────────┐
                    │  (idle state, blinks every    │                                │
                    │   10 frames)                  │                                │
                    └──┬───────┬────────┬──────────┘                                │
                       │       │        │                                           │
            ┌──────────┘       │        └──────────┐                                │
            ▼                  ▼                    ▼                                │
    ┌───────────────┐ ┌───────────────┐ ┌──────────────────┐                        │
    │   WALKING     │ │   SCANNING    │ │     GLITCH       │                        │
    │ (2-6 steps)   │ │ (15 frames)   │ │ (15 frames)      │  autoresets after N    │
    │ shuffles side │ │ eyes scan →   │ │ random noise     │  frames → WAITING      │
    └───────┬───────┘ └───────┬───────┘ └────────┬─────────┘                        │
            └─────────────────┴──────────────────┘                                  │
                                                                                    │
    External triggers (on_event):                                                   │
      THINKING ─────────────► THINKING state (15 frames) ──────────────────────────┘
      SUCCESS  ─────────────► SUCCESS state  (30 frames) ──────────────────────────┘
      ERROR    ─────────────► CONFUSED state (30 frames) ──────────────────────────┘
      IDLE     ─────────────► WAITING state  (immediate) ──────────────────────────┘
```

### State Details

| State | Trigger | Eye Render | Duration | Meaning |
|---|---|---|---|---|
| `SLEEP` | Startup | blank `"   "` | ~3s (20 frames) | Bridge initializing, no agent activity yet |
| `WAKING` | Auto after SLEEP | `"." → " ░ "` | ~1.5s (10 frames) | Bridge ready, agent waking up |
| `WAITING` | Auto after WAKING or any autoreset | blinks between 2-row/3-row | indefinite | Agent idle, awaiting user input |
| `WALKING` | Random (~5% chance/frame while WAITING) | blink | 2-6 horizontal steps | Agent processing internally, low-level background activity |
| `THINKING` | `on_event('THINKING')` | `⠶` spinner | indefinite until event | Agent is formulating a response, decomposing a task, or evaluating options |
| `SCANNING` | Random (~2% chance) | left→center→right scan | ~2.25s (15 frames) | Agent reading workspace files or searching codebase |
| `CONFUSED` | `on_event('ERROR')` | `?` | ~4.5s (30 frames) | Tool execution failed, permission denied, or unexpected output |
| `SUCCESS` | `on_event('SUCCESS')` | `!` / `^` bounce | ~4.5s (30 frames) | Task completed successfully, file written, tool returned |
| `GLITCH` | Random (~1% chance) | random noise chars | ~2.25s (15 frames) | Simulated "data corruption" — purely cosmetic easter egg |

---

## Relationship to Agent Actions

The mascot is wired into the bridge's event system. Every significant agent action maps to a visual state:

```
Agent Event                              Mascot State
──────────────────────────────────────────────────────────
Bridge startup, loading plugins          SLEEP → WAKING
Awaiting user input                      WAITING
Communicator sends message to Gemini     THINKING
Overseer decomposes task                 THINKING
Specialist executes tool (read_file)     SCANNING
Specialist executes tool (write_file)    SUCCESS
Specialist executes tool (shell_exec)    SCANNING
Permission check: granted                SUCCESS
Permission check: denied                 CONFUSED
Tool returns error                       CONFUSED
Task completed successfully              SUCCESS
Checkpoint created                       SUCCESS
Between user queries (background idle)   WAITING (with random WALKING/SCANNING/GLITCH)
```

The mapping is in `src/gemini_bridge.py` event hooks. The mascot is purely cosmetic — it doesn't affect agent behavior. If the terminal is too small (`cols < 100`), the mascot hides itself automatically.

---

## Architecture

```
mascot/
├── mascot_sim.py        # Standalone simulation (329 LOC, zero deps)
└── README.md            # This file (comprehensive docs)
```

The production version lives in `src/gfx/mascot_tui.py` (255 LOC) and is instantiated in `src/gemini_bridge.py` with a threading-based update loop:

```python
# In gemini_bridge.py startup:
mascot = Mascot()
mascot_thread = threading.Thread(target=mascot.update, daemon=True)
mascot_thread.start()

# During agent execution:
mascot.on_event('THINKING')
# After tool success:
mascot.on_event('SUCCESS')
# On error:
mascot.on_event('ERROR')
```

### Terminal Requirements

- Minimum width: 100 columns
- ANSI escape sequence support
- SIGWINCH handling for resize
- Non-blocking stdin (interactive mode only)

---

## Running Standalone

```bash
# Interactive key-controlled mode (keys 1-9 switch states)
python mascot/mascot_sim.py

# Auto-demo cycling all states
python mascot/mascot_sim.py --demo

# Start in a specific state
python mascot/mascot_sim.py --state THINKING

# Headless (no output)
python mascot/mascot_sim.py --silent
```

The simulation is fully self-contained — copy `mascot/` to any machine with Python 3.10+ and it runs immediately. No pip install needed.
