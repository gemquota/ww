#!/usr/bin/env python3
"""
Standalone Mascot Simulation — extracted from ww/src/gfx/mascot_tui.py.
Self-contained, no dependencies beyond stdlib. Run it anywhere.

Usage:
  python mascot_sim.py                  # interactive simulation
  python mascot_sim.py --demo           # auto-demo cycling through states
  python mascot_sim.py --state THINKING # start in a specific state
"""
import sys
import time
import shutil
import signal
import threading
import random
import argparse

MOVE = "\033[{y};{x}H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
SAVE_CURSOR = "\033[s"
RESTORE_CURSOR = "\033[u"
COLOR_RESET = "\033[0m"
COLOR_WHITE = "\033[37m"


class Mascot:
    """Terminal mascot with animated states. Fully self-contained."""

    STATES = ['SLEEP', 'WAKING', 'WAITING', 'WALKING', 'THINKING',
              'SCANNING', 'CONFUSED', 'SUCCESS', 'GLITCH']

    def __init__(self):
        self.silent = False
        self.width = 8
        self.height = 9
        self.state = 'SLEEP'
        self.frame = 0
        self.running = True
        self.lock = threading.Lock()
        self._shutdown_event = threading.Event()

        cols, rows = shutil.get_terminal_size()
        self.max_x = cols - self.width - 1
        self.min_x = int(cols * 0.85)
        self.current_x = self.max_x
        self.target_x = self.max_x
        self.direction = -1

        self._original_sigwinch = signal.getsignal(signal.SIGWINCH)
        signal.signal(signal.SIGWINCH, self._handle_resize)

        self.torso_top = " ███████"
        self.torso_side = " █     █"
        self.torso_bottom = " ███████"

    def get_eye_and_torso(self):
        if self.state in ['WAITING', 'WALKING']:
            is_up = (self.frame // 10) % 2 == 0
            if is_up:
                return [" ░ ", "   "], 4
            else:
                return ["   ", " ░ ", "   "], 5
        if self.state == 'SLEEP':
            return ["   ", "   ", "   "], 5
        if self.state == 'WAKING':
            if self.frame < 4:
                return ["   ", "   ", " . "], 5
            return ["   ", " ░ ", "   "], 5
        if self.state == 'SCANNING':
            phases = [["░  ", "   ", "   "], ["   ", " ░ ", "   "], ["   ", "   ", "  ░"]]
            return phases[self.frame % 3], 5
        if self.state == 'THINKING':
            dots = [" ⠶ ", "   ", "   "] if (self.frame // 2) % 2 == 0 else ["   ", " ⠶ ", "   "]
            return dots, 5
        if self.state == 'CONFUSED':
            return [" ? ", "   ", "   "], 5
        if self.state == 'SUCCESS':
            char = " ! " if (self.frame // 3) % 2 == 0 else " ^ "
            return [char, "   ", "   "], 5
        if self.state == 'GLITCH':
            noise = "".join(random.choice("░▒▓█ ") for _ in range(3))
            return [noise, noise, noise], 5
        return ["   ", " ░ ", "   "], 5

    def get_legs(self):
        if self.state != 'WALKING':
            return [" █     █", " █     █"]
        step_phase = (self.frame // 2) % 2
        if step_phase == 0:
            return [" █     █", "       █"]
        else:
            return [" █     █", " █      "]

    def draw(self):
        if self.silent:
            return
        cols, rows = shutil.get_terminal_size()
        self.max_x = cols - self.width - 1
        self.min_x = int(cols * 0.85)

        eye_rows, head_h = self.get_eye_and_torso()
        legs = self.get_legs()
        color = COLOR_WHITE
        base_y = rows - 3

        sys.stdout.write(SAVE_CURSOR)
        sys.stdout.write(HIDE_CURSOR)

        clear_width = cols - self.min_x + 1
        for i in range(11):
            ty = rows - i - 2
            if ty < 1:
                continue
            sys.stdout.write(MOVE.format(y=ty, x=self.min_x))
            sys.stdout.write(" " * clear_width)

        footer = "━" * (self.min_x - 2)
        sys.stdout.write(MOVE.format(y=rows - 1, x=1))
        sys.stdout.write(f"\033[34m{footer}\033[0m")

        for i, line in enumerate(legs):
            sys.stdout.write(MOVE.format(y=base_y + i, x=self.current_x))
            sys.stdout.write(f"{color}{line}\033[0m")

        torso_connector_h = 2
        for i in range(torso_connector_h):
            sys.stdout.write(MOVE.format(y=base_y - 1 - i, x=self.current_x))
            sys.stdout.write(f"{color}{self.torso_bottom}{COLOR_RESET}")

        for i, row in enumerate(reversed(eye_rows)):
            sys.stdout.write(MOVE.format(y=base_y - 1 - torso_connector_h - i, x=self.current_x))
            content = f" █ {row} █"
            sys.stdout.write(f"{color}{content}{COLOR_RESET}")

        top_y = base_y - 1 - torso_connector_h - len(eye_rows)
        sys.stdout.write(MOVE.format(y=top_y, x=self.current_x))
        sys.stdout.write(f"{color}{self.torso_top}{COLOR_RESET}")

        sys.stdout.write(RESTORE_CURSOR)
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    def set_state(self, state: str):
        """Set mascot state from external code."""
        if state not in self.STATES:
            return
        with self.lock:
            self.state = state
            self.frame = 0

    def on_event(self, event_type: str):
        if self.silent:
            return
        with self.lock:
            mapping = {
                'THINKING': 'THINKING', 'SUCCESS': 'SUCCESS', 'ERROR': 'CONFUSED',
                'IDLE': 'WAITING', 'SCANNING': 'SCANNING',
            }
            self.state = mapping.get(event_type, 'WAITING')
            self.frame = 0

    def _handle_resize(self, signum=None, frame=None):
        try:
            cols, rows = shutil.get_terminal_size()
            with self.lock:
                self.max_x = cols - self.width - 1
                self.min_x = int(cols * 0.85)
                if self.current_x > self.max_x:
                    self.current_x = self.max_x
                if self.current_x < self.min_x:
                    self.current_x = self.min_x
        except Exception:
            pass

    def stop(self):
        with self.lock:
            self.running = False
        self._shutdown_event.set()
        try:
            signal.signal(signal.SIGWINCH, self._original_sigwinch or signal.SIG_DFL)
        except Exception:
            pass

    def shutdown(self):
        self.stop()
        if self.silent:
            return
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.write(COLOR_RESET)
        sys.stdout.flush()

    def update(self):
        while self.running and not self._shutdown_event.is_set():
            with self.lock:
                self.frame += 1
                if self.state == 'SLEEP' and self.frame > 20:
                    self.state = 'WAKING'
                    self.frame = 0
                elif self.state == 'WAKING' and self.frame > 10:
                    self.state = 'WAITING'
                    self.frame = 0
                elif self.state == 'WAITING':
                    r = random.random()
                    if r < 0.05:
                        self.state = 'WALKING'
                        steps = random.randint(2, 6)
                        if self.current_x >= self.max_x:
                            self.direction = -1
                        elif self.current_x <= self.min_x:
                            self.direction = 1
                        else:
                            self.direction = random.choice([-1, 1])
                        self.target_x = self.current_x + (self.direction * steps)
                    elif r < 0.07:
                        self.state = 'SCANNING'
                        self.frame = 0
                    elif r < 0.08:
                        self.state = 'GLITCH'
                        self.frame = 0
                elif self.state == 'WALKING':
                    if self.current_x == self.target_x:
                        self.state = 'WAITING'
                    else:
                        self.current_x += self.direction
                        self.current_x = max(self.min_x, min(self.max_x, self.current_x))
                        if self.current_x in [self.min_x, self.max_x]:
                            self.state = 'WAITING'
                elif self.state in ['SCANNING', 'GLITCH'] and self.frame > 15:
                    self.state = 'WAITING'
                    self.frame = 0
                elif self.state in ['CONFUSED', 'SUCCESS'] and self.frame > 30:
                    self.state = 'WAITING'
                    self.frame = 0
            self.draw()
            time.sleep(0.15)


def run_demo(mascot):
    """Cycle through all mascot states automatically."""
    states = ['SLEEP', 'WAITING', 'THINKING', 'SCANNING', 'CONFUSED', 'SUCCESS', 'GLITCH']
    try:
        while mascot.running:
            for s in states:
                mascot.set_state(s)
                time.sleep(3)
    except KeyboardInterrupt:
        pass


def run_interactive(mascot):
    """Interactive key-controlled mascot simulation."""
    import sys
    sys.stdout.write("\033[2J\033[H")
    status_y = 3
    print(f"{'=' * 50}")
    print("  MASCOT SIMULATION")
    print(f"{'=' * 50}")
    print("  Keys:")
    print("    1 SLEEP    2 WAKING   3 WAITING")
    print("    4 WALKING  5 THINKING 6 SCANNING")
    print("    7 CONFUSED 8 SUCCESS  9 GLITCH")
    print("    0 IDLE     q QUIT")
    print(f"{'=' * 50}")
    key_hint = ""

    # Start the mascot update thread
    t = threading.Thread(target=mascot.update, daemon=True)
    t.start()
    time.sleep(0.5)
    mascot.set_state('SLEEP')

    try:
        while mascot.running:
            sys.stdout.write(MOVE.format(y=status_y + 7, x=1))
            sys.stdout.write(f"  Current state: \033[1m{mascot.state}\033[0m    {key_hint}")
            sys.stdout.write(MOVE.format(y=status_y + 8, x=1))
            sys.stdout.write("  Press key: ")
            sys.stdout.flush()
            
            key = sys.stdin.read(1)
            if key == 'q':
                break
            mapping = {
                '1': 'SLEEP', '2': 'WAKING', '3': 'WAITING', '4': 'WALKING',
                '5': 'THINKING', '6': 'SCANNING', '7': 'CONFUSED', '8': 'SUCCESS',
                '9': 'GLITCH', '0': 'WAITING',
            }
            if key in mapping:
                mascot.set_state(mapping[key])
                key_hint = f"→ {mapping[key]}"
    except KeyboardInterrupt:
        pass
    finally:
        mascot.shutdown()
        sys.stdout.write(f"\n\n{'=' * 50}\n  Simulation ended.\n{'=' * 50}\n")


def main():
    parser = argparse.ArgumentParser(description="Standalone Mascot Simulation")
    parser.add_argument("--demo", action="store_true", help="Auto-demo cycling through states")
    parser.add_argument("--state", choices=Mascot.STATES, default=None,
                        help="Initial state")
    parser.add_argument("--silent", action="store_true", help="Run without display")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda s, f: (sys.stdout.write(SHOW_CURSOR), sys.exit(0)))

    mascot = Mascot()
    if args.silent:
        mascot.silent = True

    if args.demo:
        run_demo(mascot)
    elif args.state:
        mascot.set_state(args.state)
        try:
            mascot.update()
        except KeyboardInterrupt:
            pass
    else:
        run_interactive(mascot)

    mascot.shutdown()


if __name__ == "__main__":
    main()
