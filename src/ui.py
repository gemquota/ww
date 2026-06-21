"""
UIAdapter Protocol — Decouples UI from business logic.

Allows the bridge to run in multiple modes:
- TerminalUIAdapter: Interactive TUI (colorama + prompt_toolkit)
- SilentUIAdapter: Headless/CI/script mode (no ANSI codes, auto-approve)
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable
from pathlib import Path


class UIAdapter(ABC):
    """Abstract interface for all user interaction.
    
    Implementations handle rendering, approval prompts, and status
    display without business logic files knowing the UI layer.
    """

    @abstractmethod
    async def request_approval(self, prompt: str, timeout: Optional[float] = None) -> bool:
        """Ask the user for approval. Returns True if approved."""
        ...

    @abstractmethod
    def log_status(self, emoji: str, title: str, detail: str = "") -> None:
        """Display a status message."""
        ...

    @abstractmethod
    def display_diff(self, diff_text: str) -> None:
        """Show a diff to the user."""
        ...

    @abstractmethod
    def display_message(self, message: str, style: str = "info") -> None:
        """Display a message. Style: info, success, warning, error."""
        ...


class TerminalUIAdapter(UIAdapter):
    """Interactive terminal UI using prompt_toolkit for async approval."""

    def __init__(self, telemetry=None):
        self.telemetry = telemetry
        self._approval_lock = False

    async def request_approval(self, prompt: str, timeout: Optional[float] = None) -> bool:
        """Async approval prompt — does NOT block the event loop."""
        from colorama import Fore, Style
        from prompt_toolkit import PromptSession
        from prompt_toolkit.formatted_text import HTML

        print(f"\n  {Fore.YELLOW}⚠ {prompt}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Options: {Fore.GREEN}y{Fore.WHITE}/{Fore.RED}n{Fore.WHITE}, "
              f"{Fore.GREEN}a{Fore.WHITE}lways, {Fore.RED}n{Fore.WHITE}ever{Style.RESET_ALL}")
        
        session = PromptSession()
        try:
            result = await session.prompt_async("  > ")
        except (EOFError, KeyboardInterrupt):
            return False

        result = result.strip().lower()
        if result in ("y", "yes"):
            return True
        elif result == "a" or result == "always":
            return True  # Caller should handle "always" via PermissionManager
        else:
            return False

    def log_status(self, emoji: str, title: str, detail: str = "") -> None:
        """Display a colored status line."""
        import datetime
        from colorama import Fore, Style
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        ts = f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL}"
        t = f"{Fore.CYAN}{title}{Style.RESET_ALL}"
        d = f" {Fore.WHITE}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"  {ts} {emoji} {t}{d}")
        if self.telemetry:
            self.telemetry.log_interaction("system", f"{emoji} {title}: {detail}", "status")

    def display_diff(self, diff_text: str) -> None:
        """Print a diff with color."""
        from colorama import Fore, Style
        for line in diff_text.split("\n"):
            if line.startswith("+"):
                print(f"  {Fore.GREEN}{line}{Style.RESET_ALL}")
            elif line.startswith("-"):
                print(f"  {Fore.RED}{line}{Style.RESET_ALL}")
            else:
                print(f"  {line}")

    def display_message(self, message: str, style: str = "info") -> None:
        """Display a styled message."""
        from colorama import Fore, Style
        colors = {"info": Fore.WHITE, "success": Fore.GREEN,
                  "warning": Fore.YELLOW, "error": Fore.RED}
        c = colors.get(style, Fore.WHITE)
        print(f"  {c}{message}{Style.RESET_ALL}")


class SilentUIAdapter(UIAdapter):
    """Non-interactive adapter for script/CI mode.
    Auto-approves everything, no ANSI codes, no prompts."""

    async def request_approval(self, prompt: str, timeout: Optional[float] = None) -> bool:
        return True  # Auto-approve in silent mode

    def log_status(self, emoji: str, title: str, detail: str = "") -> None:
        pass  # No output in silent mode

    def display_diff(self, diff_text: str) -> None:
        pass

    def display_message(self, message: str, style: str = "info") -> None:
        pass


class ApprovalUIAdapter(UIAdapter):
    """Adapter that always asks for approval (non-blocking)."""

    def __init__(self, telemetry=None):
        self.telemetry = telemetry

    async def request_approval(self, prompt: str, timeout: Optional[float] = None) -> bool:
        from colorama import Fore, Style
        from prompt_toolkit import PromptSession
        print(f"\n  {Fore.YELLOW}⚠ {prompt}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Allow? {Fore.GREEN}y{Fore.WHITE}/{Fore.RED}n{Fore.WHITE}:{Style.RESET_ALL}")
        session = PromptSession()
        try:
            result = await session.prompt_async("  > ")
        except (EOFError, KeyboardInterrupt):
            return False
        return result.strip().lower() in ("y", "yes")

    def log_status(self, emoji: str, title: str, detail: str = "") -> None:
        import datetime
        from colorama import Fore, Style
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        ts = f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL}"
        t = f"{Fore.CYAN}{title}{Style.RESET_ALL}"
        d = f" {Fore.WHITE}{detail}{Style.RESET_ALL}" if detail else ""
        print(f"  {ts} {emoji} {t}{d}")

    def display_diff(self, diff_text: str) -> None:
        pass

    def display_message(self, message: str, style: str = "info") -> None:
        from colorama import Fore, Style
        colors = {"info": Fore.WHITE, "success": Fore.GREEN,
                  "warning": Fore.YELLOW, "error": Fore.RED}
        c = colors.get(style, Fore.WHITE)
        print(f"  {c}{message}{Style.RESET_ALL}")
"""
UI utilities: visual hierarchy, output folding, theming, progress display.
Addresses V4-U1 through U5: UI & Visual Design
"""


import sys
import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, List
from colorama import Fore, Back, Style


# ── Spacing constants (addresses U3) ───────────────────────────
INDENT = "  "
SECTION_BORDER = "─" * 60


def render_box(title: str, content: str, width: int = 60) -> str:
    """Render a box with title and content using consistent borders."""
    lines = [
        f"  {Fore.CYAN}╭{'─' * width}╮{Style.RESET_ALL}",
        f"  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}{title}{Style.RESET_ALL}{' ' * (width - len(title) - 2)}  {Fore.CYAN}│{Style.RESET_ALL}",
    ]
    for line in content.split("\n"):
        wrapped = line[:width] if len(line) > width else line
        lines.append(f"  {Fore.CYAN}│{Style.RESET_ALL}  {wrapped}{' ' * (width - len(wrapped))}  {Fore.CYAN}│{Style.RESET_ALL}")
    lines.append(f"  {Fore.CYAN}╰{'─' * width}╯{Style.RESET_ALL}")
    return "\n".join(lines)


# ── Visual hierarchy (addresses U1) ────────────────────────────

class MessageLevel(Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"
    SUCCESS = "SUCCESS"


LEVEL_CONFIG = {
    MessageLevel.CRITICAL: {
        "prefix": f"{Back.RED}{Fore.WHITE} ! ",  # RED BACKGROUND
        "suffix": f" {Style.RESET_ALL}",
        "color": Fore.RED,
        "emoji": "🔴",
        "label": "ACTION REQUIRED",
    },
    MessageLevel.WARNING: {
        "prefix": f"{Back.YELLOW}{Fore.BLACK} ▲ ",
        "suffix": f" {Style.RESET_ALL}",
        "color": Fore.YELLOW,
        "emoji": "🟡",
        "label": "WARNING",
    },
    MessageLevel.INFO: {
        "prefix": "",
        "suffix": "",
        "color": Fore.CYAN,
        "emoji": "🔵",
        "label": "INFO",
    },
    MessageLevel.SUCCESS: {
        "prefix": "",
        "suffix": "",
        "color": Fore.GREEN,
        "emoji": "🟢",
        "label": "OK",
    },
}


def format_message(level: MessageLevel, message: str, detail: str = "") -> str:
    """Format a message with the appropriate visual tier."""
    cfg = LEVEL_CONFIG[level]
    detail_str = f" {detail}" if detail else ""
    return f"  {cfg['emoji']} {cfg['prefix']}[{cfg['label']}]{cfg['suffix']} {cfg['color']}{message}{Style.RESET_ALL}{Fore.WHITE}{detail_str}{Style.RESET_ALL}"


# ── Output folding (addresses U2) ──────────────────────────────

def fold_output(text: str, max_lines: int = 6, label: str = "output") -> str:
    """Fold long output: show first N lines, count, last N lines."""
    lines = text.split("\n")
    if len(lines) <= max_lines + 2:
        return text
    
    first = lines[:max_lines // 2]
    last = lines[-(max_lines // 2):]
    hidden = len(lines) - max_lines
    
    return "\n".join(first + [f"{Fore.WHITE}--- ({hidden} more lines) ---{Style.RESET_ALL}"] + last)


# ── Progress spinner (addresses U4) ────────────────────────────

class ProgressSpinner:
    """Animated progress indicator using \r overwriting."""
    
    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, message: str = "Processing"):
        self._message = message
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0
    
    def start(self):
        self._running = True
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
    
    def _animate(self):
        i = 0
        while self._running and sys.stdout.isatty():
            elapsed = time.monotonic() - self._start_time
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(f"\r  {frame} {self._message} [{elapsed:.1f}s]  ")
            sys.stdout.flush()
            time.sleep(0.15)
            i += 1
        sys.stdout.write(f"\r{' ' * 60}\r")
        sys.stdout.flush()
    
    def stop(self, success: bool = True):
        self._running = False
        if self._thread:
            self._thread.join(timeout=0.5)
        elapsed = time.monotonic() - self._start_time
        icon = "✅" if success else "❌"
        sys.stdout.write(f"\r  {icon} {self._message} [{elapsed:.1f}s]\n")
        sys.stdout.flush()


# ── Theme system (addresses U5) ────────────────────────────────

@dataclass
class Theme:
    """Semantic color theme for the bridge UI."""
    primary: str = Fore.CYAN
    success: str = Fore.GREEN
    error: str = Fore.RED
    warning: str = Fore.YELLOW
    muted: str = Fore.WHITE
    highlight: str = Fore.MAGENTA


DARK_THEME = Theme(
    primary=Fore.CYAN,
    success=Fore.GREEN,
    error=Fore.RED,
    warning=Fore.YELLOW,
    muted=Fore.WHITE,
    highlight=Fore.MAGENTA,
)

LIGHT_THEME = Theme(
    primary=Fore.BLUE,
    success=Fore.GREEN,
    error=Fore.RED,
    warning=Fore.MAGENTA,
    muted=Fore.BLACK,
    highlight=Fore.CYAN,
)


def detect_theme() -> Theme:
    """Auto-detect terminal background and return appropriate theme."""
    try:
        import subprocess
        result = subprocess.run(
            ["xtermcontrol", "--get-bg"],
            capture_output=True, text=True, timeout=1
        )
        bg = result.stdout.strip().lower()
        if bg and ("255 255 255" in bg or "white" in bg):
            return LIGHT_THEME
    except Exception:
        pass
    return DARK_THEME


# === Consolidated TUI helpers (SPA Phase 1) ===

def get_compact_time() -> str:
    """Return compact timestamp for status display."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def log_status(emoji: str, title: str, detail: str = "") -> None:
    """Log a status message with emoji (terminal-agnostic version)."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    msg = f"  [{ts}] {emoji} {title}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def render_message_box(title: str, content: str, width: int = 60) -> str:
    """Render a titled message box. Thin wrapper around render_box."""
    return render_box(title, content, width)


def build_status_line(emoji: str, title: str, detail: str = "") -> str:
    """Build a status line string without printing it."""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"  [{ts}] {emoji} {title}"
    if detail:
        line += f" — {detail}"
    return line


# ── Merged from ux_patterns.py (# UX patterns) ──
class InteractionMode(Enum):
    COMMAND = "command"       # Direct command input
    MENU = "menu"             # Menu-driven interaction
    FORM = "form"             # Form-filling interaction
    WIZARD = "wizard"         # Step-by-step guided flow


class UXPattern:
    """A reusable UX interaction pattern."""

    def __init__(self, name: str, mode: InteractionMode, 
                 confirm_before_destructive: bool = True,
                 show_progress: bool = True,
                 error_message: str = ""):
        self.name = name
        self.mode = mode
        self.confirm = confirm_before_destructive
        self.show_progress = show_progress
        self.error_message = error_message

    def get_prompt(self) -> str:
        """Get the user prompt for this pattern."""
        return f"[{self.name}]"

    def format_error(self, context: str = "") -> str:
        """Format an error message for this pattern."""
        base = self.error_message or "An error occurred"
        if context:
            return f"❌ {base}: {context}"
        return f"❌ {base}"


class TerminalUX:
    """Terminal UX helper for consistent interaction design."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    @staticmethod
    def error(message: str, suggestion: str = "") -> str:
        """Format an error message with optional suggestion."""
        result = f"❌ {message}"
        if suggestion:
            result += f"\n💡 {suggestion}"
        return result

    @staticmethod
    def warning(message: str) -> str:
        return f"⚠️ {message}"

    @staticmethod
    def success(message: str) -> str:
        return f"✅ {message}"

    @staticmethod
    def info(message: str) -> str:
        return f"ℹ️ {message}"

    @staticmethod
    def step(current: int, total: int, message: str) -> str:
        return f"[{current}/{total}] {message}"

    @staticmethod
    def progress_bar(fraction: float, width: int = 20) -> str:
        filled = int(fraction * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {int(fraction * 100)}%"


class ThemeManager:
    """Manages visual theme consistency."""

    def __init__(self):
        self.themes = {
            "default": {
                "primary": "#58a6ff",
                "background": "#0d1117",
                "surface": "#161b22",
                "border": "#30363d",
                "text": "#e6edf3",
                "text_dim": "#8b949e",
                "success": "#3fb950",
                "warning": "#d29922",
                "error": "#f85149",
            },
            "high_contrast": {
                "primary": "#1f6feb",
                "background": "#ffffff",
                "surface": "#f6f8fa",
                "border": "#d0d7de",
                "text": "#1f2328",
                "text_dim": "#656d76",
                "success": "#1a7f37",
                "warning": "#9a6700",
                "error": "#cf222e",
            },
            "dark_high_contrast": {
                "primary": "#409cff",
                "background": "#000000",
                "surface": "#0a0a0a",
                "border": "#7a828e",
                "text": "#ffffff",
                "text_dim": "#b1b9c7",
                "success": "#56d364",
                "warning": "#d29922",
                "error": "#f85149",
            },
        }

    def get_theme(self, name: str = "default") -> dict:
        return self.themes.get(name, self.themes["default"])

    def list_themes(self) -> List[str]:
        return list(self.themes.keys())
