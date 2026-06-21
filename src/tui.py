"""
TUI Module — Terminal UI components for the WW Bridge.

Responsibility: prompt_toolkit session, header, toolbar, keybindings,
status logging, and color utilities. No business logic.
"""

import datetime
from colorama import Fore, Style
from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.key_binding import KeyBindings

from src.core.context import BridgeContext


from src.ui import get_compact_time


def log_status(ctx: BridgeContext, emoji: str, title: str, detail: str = "") -> None:
    """Print a timestamped status line and log to telemetry."""
    timestamp = f"{Fore.WHITE}[{get_compact_time()}]{Style.RESET_ALL}"
    title_str = f"{Fore.CYAN}{title}{Style.RESET_ALL}"
    detail_str = f" {Fore.WHITE}{detail}{Style.RESET_ALL}" if detail else ""
    print(f"  {timestamp} {emoji} {title_str}{detail_str}")
    if ctx.telemetry:
        ctx.telemetry.log_interaction("system", f"{emoji} {title}: {detail}", "status")


def get_header() -> str:
    """Render the ASCII robot header."""
    colors = [
        "\033[38;2;255;85;85m",   # Red
        "\033[38;2;255;170;0m",   # Orange
        "\033[38;2;255;255;85m",  # Yellow
        "\033[38;2;85;255;85m",   # Green
        "\033[38;2;85;255;255m",  # Cyan
        "\033[38;2;85;85;255m",   # Blue
        "\033[38;2;255;85;255m",  # Magenta
    ]
    reset = "\033[0m"

    robot = [
        "      ╭────────╮      ",
        "      │ █▀▀▀█  │  █   ",
        "   ╭──┤ █ ◕ █  ├──▀   ",
        "   │  │ █▄▄▄█  │      ",
        "   ╰──┤        ├──╮   ",
        "      │ █▀▀▀█  │  │   ",
        "      │ █   █  │  │   ",
        "      ╰─█───█──╯──╯   ",
        "        █   █         ",
        "       ▀▀   ▀▀        "
    ]

    header_text = "   🧠 WW NEURAL BRIDGE - V3.0\n"
    output = "\n"
    for i, line in enumerate(robot):
        color = colors[i % len(colors)]
        output += f"   {color}{line}{reset}\n"
    output += f"\n{colors[3]}{header_text}{reset}"
    output += "   " + "═" * 30 + "\n"
    return output


def get_bottom_toolbar(ctx: BridgeContext) -> HTML:
    """Render the bottom toolbar with token utilization."""
    mode = "VERBOSE" if ctx.verbose_mode else "COMPACT"
    report = ctx.conversation.get_token_report() if ctx.conversation else "0/0 tokens"
    util = ctx.conversation.get_utilization() if ctx.conversation else 0.0
    bar_len = 10
    filled = int(util * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    pressure = ""
    if util >= 0.90:
        pressure = f" {Fore.RED}⚠ {util:.0%}{Style.RESET_ALL}"
    elif util >= 0.75:
        pressure = f" {Fore.YELLOW}{util:.0%}{Style.RESET_ALL}"
    else:
        pressure = f" {Fore.GREEN}{util:.0%}{Style.RESET_ALL}"
    return HTML(
        f' <b>[WW]</b> {ctx.bridge_status} | {bar}{pressure} | '
        f'<b>{mode}</b> | {report} | <b>^E</b> toggle'
    )


def build_keybindings(ctx: BridgeContext) -> KeyBindings:
    """Create keybindings for the prompt session."""
    kb = KeyBindings()

    @kb.add('c-e')
    def _(event):
        ctx.verbose_mode = not ctx.verbose_mode
        log_status(ctx, "🔧", f"Verbose mode: {'ON' if ctx.verbose_mode else 'OFF'}")
        event.app.invalidate()

    return kb


def create_prompt_style() -> PtStyle:
    """Create the prompt_toolkit style."""
    return PtStyle.from_dict({
        'bottom-toolbar': 'bg:#333333 #ffffff',
    })


def build_prompt_html(ctx: BridgeContext) -> HTML:
    """Build the p10k-inspired prompt HTML."""
    mode_segment = " \uf0c2 GEMINI "
    mode_color = "#58a6ff"
    dir_name = ctx.workspace_root.name

    return HTML(
        f'<style bg="{mode_color}" fg="#000000">{mode_segment}</style>'
        f'<style bg="#30363d" fg="{mode_color}">\ue0b0</style>'
        f'<style bg="#30363d" fg="#ffffff"> \uf07b {dir_name} </style>'
        f'<style fg="#30363d">\ue0b0</style> '
    )
