"""
Deprecation policy utilities for internal APIs.
Addresses NEW-A1#4 (Dr. Kira Ivanova).
"""
import warnings
import functools
from typing import Callable, Optional


def deprecated(
    version: str = "",
    alternative: Optional[str] = None,
    removal_version: Optional[str] = None,
    category: type = DeprecationWarning,
) -> Callable:
    """Decorator marking a function as deprecated.

    Args:
        version: Version when the deprecation was introduced (e.g. '2.0.0')
        alternative: Name of the replacement function/class
        removal_version: Version when the deprecated item will be removed
        category: Warning category (default: DeprecationWarning)

    Usage:
        @deprecated(version='2.0.0', alternative='new_function')
        def old_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            parts = []
            if version:
                parts.append(f"since v{version}")
            if alternative:
                parts.append(f"use {alternative} instead")
            if removal_version:
                parts.append(f"will be removed in v{removal_version}")
            msg = f"{func.__name__} is deprecated"
            if parts:
                msg += f" ({'; '.join(parts)})"
            warnings.warn(msg, category, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DeprecationReporter:
    """Collects deprecation reports for CI reporting."""

    def __init__(self):
        self._reports = []

    @staticmethod
    def report(module: str, item: str, version: str, alternative: str = ""):
        """Generate a deprecation report entry."""
        entry = {
            "module": module,
            "item": item,
            "deprecated_since": version,
            "alternative": alternative,
        }
        return entry

    def add_report(self, report: dict):
        self._reports.append(report)

    def generate_markdown(self) -> str:
        """Generate a deprecation report in Markdown format."""
        if not self._reports:
            return "# Deprecation Report\n\nNo items currently deprecated."
        lines = ["# Deprecation Report", ""]
        for r in self._reports:
            alt = f" → use `{r['alternative']}`" if r.get('alternative') else ""
            lines.append(f"- `{r['module']}.{r['item']}` deprecated since v{r['deprecated_since']}{alt}")
        return "\n".join(lines)
