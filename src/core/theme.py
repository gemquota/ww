from typing import Callable, List
"""Theme definitions for TUI — SPA extraction from gemini_bridge.py."""
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


class Theme:
    """Color theme with contrast support. Default is dark mode."""
    DARK = {
        "primary": Fore.CYAN,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "muted": Fore.LIGHTBLACK_EX,
        "highlight": Fore.MAGENTA,
        "border": Fore.LIGHTBLACK_EX,
        "bg": "",
    }
    LIGHT = {
        "primary": Fore.BLUE,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "muted": Fore.LIGHTBLACK_EX,
        "highlight": Fore.MAGENTA,
        "border": Fore.LIGHTBLACK_EX,
        "bg": "",
    }
    HIGH_CONTRAST = {
        "primary": Fore.WHITE + Style.BRIGHT,
        "success": Fore.GREEN + Style.BRIGHT,
        "warning": Fore.YELLOW + Style.BRIGHT,
        "error": Fore.RED + Style.BRIGHT,
        "muted": Fore.LIGHTWHITE_EX,
        "highlight": Fore.WHITE + Style.BRIGHT,
        "border": Fore.WHITE,
        "bg": "",
    }
    
    _current = DARK
    
    @classmethod
    def set_theme(cls, name: str):
        if name == "light":
            cls._current = cls.LIGHT
        elif name == "high_contrast":
            cls._current = cls.HIGH_CONTRAST
        else:
            cls._current = cls.DARK
    
    @classmethod
    def get(cls, key: str) -> str:
        return cls._current.get(key, "")
    
    @classmethod
    def c(cls, key: str, text: str) -> str:
        """Colorize text with the given theme key."""
        return f"{cls.get(key)}{text}{Style.RESET_ALL}"
