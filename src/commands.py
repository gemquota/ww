"""
CLI commands — /docs, /help, /salvage, etc.
Addresses NEW-V5-E2#3 — hover documentation (/docs command).
"""
import pydoc
import sys
from typing import Optional


def docs_command(symbol: str) -> str:
    """Look up documentation for a symbol using pydoc."""
    try:
        help_text = pydoc.render_doc(symbol, renderer=pydoc.plaintext)
        # Truncate to reasonable length
        if len(help_text) > 2000:
            help_text = help_text[:2000] + "\n... (truncated)"
        return help_text
    except Exception as e:
        return f"No documentation found for '{symbol}': {e}"


def help_command(topic: Optional[str] = None) -> str:
    """Built-in help system."""
    if not topic:
        return """
WW Bridge Commands:
  /help [topic]    Show this help or help for a topic
  /docs <symbol>   Show documentation for a Python symbol
  /undo            Undo last operation
  /save <name>     Save current session
  /load <name>     Load a saved session
  /salvage         Attempt to recover a corrupted session

Topics: tools, sessions, plugins, configuration, tutorial
"""
    topics = {
        "tools": "Tools: read_file, write_file, file_patch, shell_exec, code_search, url_fetch, git, doc_search",
        "sessions": "Sessions persist conversation history. Use /save and /load to manage them.",
        "plugins": "Plugins extend functionality. Place .py files in the plugins directory.",
        "configuration": "Configuration via .env file. See --help for all CLI options.",
        "tutorial": "Run with --demo for a guided walkthrough.",
    }
    return topics.get(topic, f"Unknown topic: {topic}")
"""
Additional slash commands for UX improvements.
Addresses V4-W1 through W5: UX & Interaction Flow
"""


from typing import Any, Dict, Optional
from colorama import Fore, Style
from src.ui import render_box


async def cmd_task(ctx: Any, args: str) -> None:
    """Manage task-scoped conversations (/task new|status|close|list)."""
    parts = args.strip().split(None, 1) if args.strip() else ["status"]
    subcmd = parts[0].lower() if parts else "status"
    
    if not hasattr(ctx, '_tasks'):
        ctx._tasks = {}
    
    if subcmd == "new":
        name = parts[1] if len(parts) > 1 else f"task-{len(ctx._tasks) + 1}"
        ctx._tasks[name] = {"status": "active", "turns": 0}
        ctx._active_task = name
        print(f"  {Fore.GREEN}📋 Task started: {name}{Style.RESET_ALL}")
    
    elif subcmd == "status":
        if not ctx._tasks:
            print(f"  {Fore.YELLOW}No active tasks. Use /task new <name> to start one.{Style.RESET_ALL}")
            return
        active = getattr(ctx, '_active_task', None)
        for name, task in ctx._tasks.items():
            marker = "▶" if name == active else " "
            status_color = Fore.GREEN if task["status"] == "active" else Fore.WHITE
            print(f"  {marker} {status_color}{name}: {task['status']} ({task.get('turns', 0)} turns){Style.RESET_ALL}")
    
    elif subcmd == "close":
        active = getattr(ctx, '_active_task', None)
        if active and active in ctx._tasks:
            ctx._tasks[active]["status"] = "closed"
            print(f"  {Fore.GREEN}📋 Task closed: {active}{Style.RESET_ALL}")
            ctx._active_task = None
        else:
            print(f"  {Fore.YELLOW}No active task to close.{Style.RESET_ALL}")
    
    elif subcmd == "list":
        if not ctx._tasks:
            print(f"  {Fore.YELLOW}No tasks recorded.{Style.RESET_ALL}")
            return
        for name, task in ctx._tasks.items():
            print(f"  • {name}: {task['status']} ({task.get('turns', 0)} turns)")
    
    else:
        print(f"  Unknown subcommand: /task {subcmd}. Use: new|status|close|list")


async def cmd_plan(ctx: Any, args: str) -> None:
    """Show execution plan preview (W1). Placeholder for future integration."""
    print(render_box(
        "Execution Plan",
        "Plan preview will show here before tool execution.\n"
        "This is a stub for W1: Task Abstraction Layer."
    ))
