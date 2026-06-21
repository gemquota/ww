"""Tool call extraction and validation utilities."""
import re
import json
from typing import Optional, Tuple, Dict, Any


def extract_tool_call(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Extracts a tool call from the model's response.
    Expected format:
    ```tool:tool_name
    {"key": "value"}
    ```
    """
    match = re.search(r"```tool:(\w+)\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        return None
    name = match.group(1)
    args_json = match.group(2).strip()
    try:
        args = json.loads(args_json)
        return name, args
    except json.JSONDecodeError:
        return None


# ── Centralized Error Formatting ──────────────────────────────────

def classify_error(error: Exception) -> str:
    """Classify an exception into a category for user-facing messages."""
    err_str = str(error).lower()
    err_type = type(error).__name__
    
    # Authentication errors
    if any(k in err_str for k in ("auth", "credential", "token", "api key", "1psid", "unauthenticated")):
        return "AUTH"
    if err_type in ("AuthenticationError", "PermissionDenied", "AuthError"):
        return "AUTH"
    
    # Network errors
    if any(k in err_str for k in ("connection", "timeout", "dns", "reset", "refused", "network")):
        return "NETWORK"
    if err_type in ("ConnectionError", "TimeoutError", "OSError"):
        return "NETWORK"
    
    # Rate limit errors
    if any(k in err_str for k in ("rate limit", "too many", "quota", "429", "resource exhausted")):
        return "RATE_LIMIT"
    
    # Tool errors
    if any(k in err_str for k in ("tool error", "unknown tool", "tool timeout", "permission")):
        return "TOOL"
    if err_type in ("ToolError", "PermissionError", "FileNotFoundError", "ValueError"):
        return "TOOL"
    
    # Internal/system errors
    return "INTERNAL"


ERROR_ACTIONS = {
    "AUTH": "Check your .env credentials (SECURE_1PSID / SECURE_1PSIDTS). Run with --auth for setup help.",
    "NETWORK": "Check your internet connection and try again. Use --verbose for details.",
    "RATE_LIMIT": "Wait a moment before retrying. Rate limit is ~10 RPM.",
    "TOOL": "Verify the tool name and arguments. Use /help for available commands.",
    "INTERNAL": "This is an unexpected error. Use --verbose for a raw traceback.",
}

ERROR_EMOJIS = {
    "AUTH": "🔐",
    "NETWORK": "🌐",
    "RATE_LIMIT": "⏳",
    "TOOL": "🛠️",
    "INTERNAL": "💥",
}


def format_error(error: Exception, verbose: bool = False) -> str:
    """Format an error for user display with category, message, and actionable hint.
    
    In verbose mode, also includes the raw traceback.
    In normal mode, only shows the categorized summary.
    """
    category = classify_error(error)
    emoji = ERROR_EMOJIS.get(category, "❌")
    action = ERROR_ACTIONS.get(category, "Check --verbose for details.")
    msg = str(error).strip() or type(error).__name__
    # Keep message short for user display
    short_msg = msg[:200] + ("..." if len(msg) > 200 else "")
    
    result = f"  {emoji} [{category}] {short_msg}\n  → {action}"
    
    return result
