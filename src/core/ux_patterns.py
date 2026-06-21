"""UX pattern library for terminal interaction design."""
from enum import Enum
from typing import List, Optional


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
