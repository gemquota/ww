"""
UIAdapter Protocol — Decouples UI from business logic.

Allows the bridge to run in multiple modes:
- TerminalUIAdapter: Interactive TUI (colorama + prompt_toolkit)
- SilentUIAdapter: Headless/CI/script mode (no ANSI codes, auto-approve)
"""

from abc import ABC, abstractmethod
from typing import Optional


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
