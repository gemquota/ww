"""
Error translation layer: maps internal exceptions to user-facing messages.
Addresses NEW-A2#4 (Tomas Rivera).
"""
import traceback
from typing import Dict, Optional, Type, Callable


class ErrorTranslator:
    """Maps internal exceptions to user-facing messages."""

    def __init__(self):
        self._registry: Dict[Type[Exception], str] = {
            FileNotFoundError: "File not found. Check the path and try again.",
            PermissionError: "Permission denied. You may not have access to this resource.",
            ConnectionError: "Network connection failed. Check your internet connection.",
            TimeoutError: "Operation timed out. Try again or use a simpler query.",
            ValueError: "Invalid value provided. Check your input and try again.",
            KeyError: "Required key or field is missing.",
            ImportError: "A required module could not be loaded. Check dependencies.",
        }

    def register(self, exc_type: Type[Exception], message: str):
        """Register a custom exception mapping."""
        self._registry[exc_type] = message

    def translate(self, exc: Exception, include_traceback: bool = False) -> str:
        """Translate an exception to a user-friendly message."""
        # Try exact match first
        for exc_type, msg in self._registry.items():
            if type(exc) is exc_type:
                base = msg
                break
        else:
            # Check inheritance
            for exc_type, msg in self._registry.items():
                if isinstance(exc, exc_type):
                    base = msg
                    break
            else:
                base = f"An unexpected error occurred: {type(exc).__name__}"

        result = f"⚠️  {base}"
        if str(exc):
            result += f"\n   Details: {str(exc)}"

        if include_traceback:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            result += f"\n   Traceback:\n{tb}"

        return result


# Global instance
_translator = ErrorTranslator()


def translate_error(exc: Exception, include_traceback: bool = False) -> str:
    """Convenience function to translate an exception."""
    return _translator.translate(exc, include_traceback)
