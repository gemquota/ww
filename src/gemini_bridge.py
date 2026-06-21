"""
WW Neural Bridge - Frontier-Grade CLI Harness for Gemini Multi-Agent System.

A production-quality agentic coding loop featuring:
- Token-aware context window management with auto-compaction
- Fuzzy SEARCH/REPLACE editing with colorized diffs
- Granular permission/approval system for tool execution
- Git checkpoint system with /undo support
- AGENTS.md standard instruction loading
- AST-aware repository mapping
- Streaming-ready architecture with interruptibility
"""

import asyncio
import sys
import os
import re
import datetime, json
import traceback
import signal
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
from gemini_webapi import GeminiClient
from src.smart_context import get_workspace_context, read_file_surgical, get_directory_context
from src.context_manager import ConversationHistory, RepoMapper, TokenCounter
from src.permissions import PermissionManager, ApprovalPolicy, PermissionLevel
from src.diff_engine import DiffEngine
from src.checkpoint import CheckpointManager
from src.agents_loader import load_all_instructions
from colorama import Fore, Style, init as colorama_init

# ── Theme / Color Scheme ─────────────────────────────────────

from src.core.theme import Theme

class TaskDecomposer:
    """Simple task decomposition for breaking complex operations into steps."""
    
    @staticmethod
    def decompose(query: str, max_steps: int = 5) -> list:
        """Break a complex query into logical subtasks."""
        # Simple heuristic decomposition
        steps = []
        separators = [" and then ", " then ", ". then ", " after that "]
        for sep in separators:
            if sep in query.lower():
                parts = query.lower().split(sep)
                steps = [p.strip().capitalize() for p in parts if p.strip()]
                break
        
        if not steps:
            steps = [query]
        
        # Limit steps
        if len(steps) > max_steps:
            steps = steps[:max_steps]
        
        return steps
    
    @staticmethod
    def format_steps(steps: list) -> str:
        """Format decomposed steps for display."""
        if not steps:
            return ""
        lines = [f"\n  {Theme.c('highlight', '📋 Task Plan:')}"]
        for i, step in enumerate(steps, 1):
            lines.append(f"    {Theme.c('primary', str(i))}. {step}")
        return "\n".join(lines)

# Also add --theme CLI argument

from src.file_watcher import FileWatcher
from src.telemetry import TelemetryManager
from src.core.memory import MemoryManager
from src.core.healing import AutoHealer
from src.core.schemas import ToolCall
from src.bridge.event_bus import EventBus, EventType
from src.bridge.profile_manifest import AgentProfileManifest
from src.utils.error_translator import ErrorTranslator
from src.utils.deprecation import DeprecationReporter
from src.tools.registry import ToolRegistry
from src.tools.system_tools import (
    read_file, list_dir, write_file, shell_exec, git_tool,
    doc_search, request_clarification,
    code_search, file_patch, url_fetch,
    ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs,
    UpdateScratchpadArgs, GitArgs, DocSearchArgs, ClarificationArgs,
    CodeSearchArgs, FilePatchArgs, UrlFetchArgs
)
# WebGeminiClient loaded via _lazy_import()
from src.utils.validation import extract_tool_call
from src.commands import COMMAND_TABLE
from src.context import BridgeContext
from src.config import get_settings


# UI Imports
from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import clear
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.key_binding import KeyBindings

# Module-level init (called once at import time)
colorama_init(autoreset=True)
load_dotenv()

# Suppress noisy gemini_webapi debug logs
logger.remove()
logger.add(sys.stderr, level="INFO")

_settings = get_settings()
SECURE_1PSID = _settings.gemini.credentials.secure_1psid or os.getenv("SECURE_1PSID")
SECURE_1PSIDTS = _settings.gemini.credentials.secure_1psidts or os.getenv("SECURE_1PSIDTS")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or _settings.gemini.credentials.api_key if hasattr(_settings.gemini.credentials, 'api_key') else os.getenv("GEMINI_API_KEY", "")
WORKSPACE_ROOT = _settings.resolve_workspace()
telemetry = TelemetryManager(WORKSPACE_ROOT)

# --- Local LM Configuration ---


# --- Core Systems ---
conversation = ConversationHistory(context_window=_settings.context_window)
token_counter = TokenCounter()
checkpoint_mgr = CheckpointManager(WORKSPACE_ROOT)
permission_mgr = PermissionManager(WORKSPACE_ROOT, ApprovalPolicy[_settings.policy.upper().replace("-", "_")])
diff_engine = DiffEngine()

VERBOSE_MODE = False
BRIDGE_STATUS = "Idle"
AGENT_SESSIONS = {}  # Persistent sub-agent chat objects

# Initialize ToolRegistry with all system tools
tool_registry = ToolRegistry()
tool_registry.register("read_file", read_file, "Read contents of a file.", ReadFileArgs, tags=["read", "research"])
tool_registry.register("write_file", write_file, "Write contents to a file.", WriteFileArgs, tags=["write", "edit"])
tool_registry.register("list_dir", list_dir, "List files in a directory.", ListDirArgs, tags=["read", "research"])
tool_registry.register("shell_exec", shell_exec, "Execute a shell command.", ShellExecArgs, tags=["exec", "system"])
tool_registry.register("git", git_tool, "Execute git commands.", GitArgs, tags=["git", "vcs"])
tool_registry.register("doc_search", doc_search, "Search project documentation.", DocSearchArgs, tags=["read", "research"])
tool_registry.register("request_clarification", request_clarification, "Ask the user for more information.", ClarificationArgs, tags=["comm", "interrupt"])
tool_registry.register("code_search", code_search, "Search for a regex pattern across project files.", CodeSearchArgs, tags=["read", "research", "search"])
tool_registry.register("file_patch", file_patch, "Apply a surgical text replacement in a file.", FilePatchArgs, tags=["write", "edit", "patch"])
tool_registry.register("url_fetch", url_fetch, "Fetch a URL via HTTP GET with configurable timeout.", UrlFetchArgs, tags=["read", "network"])

# Set workspace root for sandboxed tool operations
from src.tools.system_tools import set_workspace_root as _set_tools_root
_set_tools_root(WORKSPACE_ROOT)
from src.tool_executor import ToolExecutor, log_status as te_log_status


tool_defs = tool_registry.get_definitions(minimalist=True)

# Initialize plugin system
plugin_scanner = None
try:
    plugin_scanner = __import__("plugins.ww_plugin", fromlist=["PluginScanner"]).PluginScanner()
except Exception:
    plugin_scanner = None
_loguru_ = __import__("loguru").logger


# Module-level core systems (initialized in initialize_bridge)
memory = None
healer = None
_shutdown_requested = False

async def _init_plugins():
    global plugin_scanner
    if not plugin_scanner:
        return
    try:
        loaded = await plugin_scanner.load_all(tool_registry)
        if loaded:
            _loguru_.info(f"Plugins loaded: {', '.join(loaded)}")
    except Exception as e:
        _loguru_.warning(f"Plugin init: {e}")

async def _shutdown_plugins():
    global plugin_scanner
    if plugin_scanner:
        try:
            await plugin_scanner.shutdown_all()
        except Exception:
            pass

def shutdown_handler(signum=None, frame=None) -> None:
    """Signal handler — sets flag for async cleanup. Does NOT run async code."""
    global _shutdown_requested
    _shutdown_requested = True


async def _cleanup_and_exit():
    """Async cleanup — flush state, save checkpoint, stop plugins, then exit."""
    global _shutdown_requested
    if not _shutdown_requested:
        return
    import sys
    print(f"\n  {Fore.YELLOW}⏻ Shutting down...{Style.RESET_ALL}")
    telemetry.end_session(summary="User exited (SIGINT).")
    try:
        memory.flush()
    except Exception:
        pass
    try:
        sig = checkpoint_mgr.create_checkpoint("auto-shutdown")
        if sig:
            print(f"  {Fore.GREEN}  Checkpoint saved: {sig}{Style.RESET_ALL}")
    except Exception:
        pass
    _loguru_.info("Shutting down plugins...")
    try:
        await file_watcher.stop()
    except Exception:
        pass
    try:
        await _shutdown_plugins()
    except Exception:
        pass
    print(f"  {Fore.GREEN}✓ Shutdown complete.{Style.RESET_ALL}")
    sys.exit(0)

from src.ui_utils import get_compact_time

def log_status(emoji: str, title: str, detail: str = "") -> None:
    """Thin wrapper delegating to tool_executor's log_status."""
    te_log_status(emoji, title, detail, telemetry)

def get_header():
    colors = [
        "\033[38;2;255;85;85m",  # Red
        "\033[38;2;255;170;0m", # Orange
        "\033[38;2;255;255;85m",# Yellow
        "\033[38;2;85;255;85m", # Green
        "\033[38;2;85;255;255m",# Cyan
        "\033[38;2;85;85;255m", # Blue
        "\033[38;2;255;85;255m" # Magenta
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

def get_bottom_toolbar():
    mode = "VERBOSE" if VERBOSE_MODE else "COMPACT"
    report = conversation.get_token_report()
    util = conversation.get_utilization()
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
    return HTML(f' <b>[WW]</b> {BRIDGE_STATUS} | {bar}{pressure} | <b>{mode}</b> | {report} | <b>^E</b> toggle')

pt_style = PtStyle.from_dict({
    'bottom-toolbar': 'bg:#333333 #ffffff',
})

kb = KeyBindings()

@kb.add('c-e')
def _(event):
    global VERBOSE_MODE
    VERBOSE_MODE = not VERBOSE_MODE
    log_status("🔧", f"Verbose mode: {'ON' if VERBOSE_MODE else 'OFF'}")
    event.app.invalidate()


async def safe_send_message(chat, message: str, max_retries: int = 3):
    global BRIDGE_STATUS
    BRIDGE_STATUS = "Processing"

    if VERBOSE_MODE:
        tokens = token_counter.count(message)
        print(f"  {Fore.WHITE}[DEBUG] Sending {tokens} tokens...{Style.RESET_ALL}")

    start_time = __import__('time').monotonic()

    for attempt in range(max_retries):
        try:
            result = await chat.send_message(message)
            BRIDGE_STATUS = "Active"

            # Task completion summary
            elapsed = __import__('time').monotonic() - start_time
            if hasattr(result, 'text') and result.text:
                input_tokens = token_counter.count(message)
                output_tokens = token_counter.count(result.text)
                log_status("✅", "Task complete",
                    f"{elapsed:.1f}s, ~{input_tokens}+{output_tokens} tokens")
            return result
        except Exception as e:
            err_msg = str(e).lower()
            wait = (2 ** attempt) + 1

            if "suspended" in err_msg:
                log_status("⚠️", "Stream Suspended", f"retry {attempt + 1}/{max_retries}")
            elif "init" in err_msg:
                log_status("❌", "Init Error", str(e))
            else:
                log_status("⚠️", "Connection Error", f"retry {attempt + 1}/{max_retries}")

            if attempt == max_retries - 1:
                BRIDGE_STATUS = "Error"
                # Attempt auto-heal diagnosis
                try:
                    report = f"Task failed after {max_retries} attempts.\nError: {e}\nMessage (truncated): {message[:500]}"
                    # Include PCG causal chains from memory for richer diagnosis
                    pcg_chains = None
                    try:
                        pcg_chains = memory.graph.get_causal_chain() if hasattr(memory, 'graph') else None
                    except Exception:
                        pass
                    fix_strategy = await healer.diagnose(report, pcg_chains=pcg_chains)
                    if fix_strategy:
                        log_status("🩺", "Auto-heal diagnosis", fix_strategy[:200])
                except Exception as he:
                    log_status("⚠️", "Auto-heal failed", str(he))
                raise e

            await asyncio.sleep(wait)

async def initialize_bridge() -> tuple:
    global BRIDGE_STATUS, memory, healer
    BRIDGE_STATUS = "Initializing"

    # Initialize core systems
    # WebGeminiClient loaded via _lazy_import()
    from src.core.healing import AutoHealer

    client = WebGeminiClient(secure_1psid=SECURE_1PSID, secure_1psidts=SECURE_1PSIDTS, api_key=GEMINI_API_KEY)
    if not await client.init():
        log_status("❌", "Failed to initialize Gemini Web client")
        return None, None, {}

    chat = client.chat
    memory = MemoryManager(session_name="default")
    healer = AutoHealer()

    # Gemini Web API mode only
    agents_instructions = load_all_instructions(WORKSPACE_ROOT)

    agents_dir = WORKSPACE_ROOT / "agents"
    agent_specs = []
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            # Reduced max_lines to 150 for leaner priming
            content = read_file_surgical(agent_file, max_lines=150)
            if content.strip():
                agent_specs.append(f"### AGENT: {agent_file.stem.upper()}\n{content}")

    agent_registry = "\n\n".join(agent_specs)
    base_instructions = ""
    base_path = WORKSPACE_ROOT / "GEM_INSTRUCTIONS.md"
    if base_path.exists():
        base_instructions = read_file_surgical(base_path, max_lines=300)

    log_status("📊", "Gathering workspace context...")
    workspace_context = get_workspace_context(str(WORKSPACE_ROOT))

    comm_path = WORKSPACE_ROOT / "agents" / "communicator.md"
    comm_instructions = read_file_surgical(comm_path, max_lines=200) if comm_path.exists() else ""

    identity_message = (
        f"YOUR IDENTITY:\n{comm_instructions}\n\n"
        f"PROJECT INSTRUCTIONS (AGENTS.md):\n{agents_instructions}\n\n"
        f"AGENT REGISTRY:\n{agent_registry}\n\n"
        f"BASE TOOL PROTOCOLS:\n{base_instructions}\n\n"
        "Acknowledge your role. I will follow up with the current workspace context."
    )

    context_message = (
        f"CURRENT WORKSPACE CONTEXT:\n{workspace_context}\n\n"
        "You are now fully primed. To summon agents or use tools, emit the tool blocks. "
        "Outputs will be fed back automatically. How can I assist you?"
    )

    identity_tokens = token_counter.count(identity_message)
    context_tokens = token_counter.count(context_message)
    conversation.set_system_prompt_tokens(identity_tokens + context_tokens)
    log_status("📐", f"Priming: {identity_tokens:,} + {context_tokens:,} tokens")

    log_status("🚀", "Initializing session...")
    await _init_plugins()
    # Skip the "Hello" message to save a turn and get straight to identity
    
    log_status("🚀", "Sending identity...")
    resp1 = await safe_send_message(chat, identity_message)
    if not resp1 or not resp1.text:
        log_status("❌", "Identity priming failed")
        return None, None, {}

    log_status("🚀", "Sending workspace context...")
    resp2 = await safe_send_message(chat, context_message)
    if resp2 and resp2.text:
        telemetry.log_interaction("communicator", resp2.text, "priming_response")
        log_status("✅", "Session primed")
    else:
        log_status("❌", "Context priming failed")
    
    BRIDGE_STATUS = "Active"

    return client, chat, {
        'client': client, 
        'chat': chat, 
        'agents_instructions': agents_instructions,
        'workspace_context': workspace_context,
        'agent_registry': agent_registry,
        'memory': memory
    }



class GracefulDegradation:
    """Context manager for graceful degradation on failures."""
    _degraded = False
    
    @classmethod
    def is_degraded(cls) -> bool:
        return cls._degraded
    
    @classmethod
    async def __aenter__(cls):
        return cls
    
    @classmethod
    async def __aexit__(cls, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            cls._degraded = True
            from loguru import logger as _loguru_
            _loguru_.warning(f"Degraded mode activated: {exc_type.__name__}: {exc_val}")
        return True  # Suppress the exception to allow graceful continuation


async def main():
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, shutdown_handler)
        loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
    except NotImplementedError:
        # Fallback for platforms without add_signal_handler support (Windows)
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    global VERBOSE_MODE, BRIDGE_STATUS

    # Create BridgeContext from module-level state
    bridge_ctx = BridgeContext(
        settings=_settings,
        workspace_root=WORKSPACE_ROOT,
        secure_1psid=SECURE_1PSID,
        secure_1psidts=SECURE_1PSIDTS,
        api_key=GEMINI_API_KEY,
        conversation=conversation,
        token_counter=token_counter,
        permission_mgr=permission_mgr,
        checkpoint_mgr=checkpoint_mgr,
        diff_engine=diff_engine,
        telemetry=telemetry,
        memory=memory,
        healer=healer,
        tool_registry=tool_registry,
        tool_defs=tool_defs,
        plugin_scanner=plugin_scanner,
        verbose_mode=VERBOSE_MODE,
        bridge_status=BRIDGE_STATUS,
        agent_sessions=AGENT_SESSIONS,
    )
    
    # Argument parsing with argparse
    import argparse
    _parser = argparse.ArgumentParser(
        prog="ww",
        description="WW Neural Bridge — Gemini Multi-Agent Coding Harness",
        epilog="Run without arguments for interactive TUI mode."
    )
    _parser.add_argument("--theme", choices=["dark", "light", "high_contrast"], default="dark", help="Color theme (dark/light/high_contrast)")
    _parser.add_argument("--show-config", action="store_true", help="Show effective configuration and exit")
    _parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    _parser.add_argument("--health", action="store_true", help="Run health check (validate credentials + API)")
    _parser.add_argument("--auth", action="store_true", help="Show credential setup instructions")
    _parser.add_argument("--script", nargs="?", const=None, default=None, metavar="QUERY",
                        help="Run a single query in script mode (JSON output)")
    _parser.add_argument("--session", metavar="NAME", help="Load a saved session on startup")
    _parser.add_argument("--demo", action="store_true", help="Run demo mode with canned conversation (no credentials needed)")
    _parser.add_argument("--use-api", action="store_true", help="Explicitly use Gemini API key instead of cookies")
    _parser.add_argument("--profile-startup", action="store_true", help="Profile startup time (print timing breakdown)")
    _args, _remaining = _parser.parse_known_args()
    
    VERBOSE_MODE = _args.verbose
    if _args.use_api:
        os.environ["WW_USE_API"] = "true"
    
    clear()
    print(get_header())

    # --health mode: validate credentials and API connectivity
    if _args.health:
        # WebGeminiClient loaded via _lazy_import()
        from colorama import Fore, Style
        
        print(f"\n  {Fore.CYAN}🔍 Health Check{Style.RESET_ALL}")
        print(f"  {'─' * 50}")
        
        # Check credentials
        if GEMINI_API_KEY:
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL} GEMINI_API_KEY found in environment")
        elif SECURE_1PSID and SECURE_1PSIDTS:
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Cookie credentials found in environment")
        else:
            print(f"  {Fore.RED}✗{Style.RESET_ALL} No credentials found. Run with --auth")
            return 4
        
        # Determine auth type
        client = WebGeminiClient(
            secure_1psid=SECURE_1PSID,
            secure_1psidts=SECURE_1PSIDTS,
            api_key=GEMINI_API_KEY
        )
        
        # Test API connectivity
        client = WebGeminiClient(secure_1psid=SECURE_1PSID, secure_1psidts=SECURE_1PSIDTS, api_key=GEMINI_API_KEY)
        print(f"  {Fore.WHITE}⏳ Testing Gemini Web API connection...{Style.RESET_ALL}")
        if await client.init():
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL} Gemini Web API initialized")
        else:
            print(f"  {Fore.RED}✗{Style.RESET_ALL} Failed to initialize Gemini Web API")
            return 1
        
        # Send ping query
        print(f"  {Fore.WHITE}⏳ Sending test query...{Style.RESET_ALL}")
        resp = await client.ask("Respond with only the word OKAY.")
        if resp and "OKAY" in resp:
            print(f"  {Fore.GREEN}✓{Style.RESET_ALL} API responded correctly")
            print(f"\n  {Fore.GREEN}✅ All checks passed.{Style.RESET_ALL}")
            return 0
        else:
            print(f"  {Fore.RED}✗{Style.RESET_ALL} API returned unexpected response: {str(resp)[:100]}")
            return 1

    # --auth mode: print credential setup instructions
    if _args.auth:
        _has_api_key = bool(GEMINI_API_KEY)
        _has_cookies = bool(SECURE_1PSID and SECURE_1PSIDTS)
        _b = f"""  {Fore.CYAN}╭{'─' * 60}╮{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Gemini Credential Setup{Style.RESET_ALL}                                        {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  WW Bridge supports TWO authentication methods:                    {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Method 1: GEMINI_API_KEY (recommended){Style.RESET_ALL}                              {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  1. Get an API key from {Fore.CYAN}https://aistudio.google.com/apikey{Style.RESET_ALL}       {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  2. Add to your {Fore.WHITE}.env{Style.RESET_ALL} file:                                        {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}     $ {{Fore.GREEN}}echo "GEMINI_API_KEY=your_key_here" >> .env{Style.RESET_ALL}           {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Method 2: Cookie-based (free tier){Style.RESET_ALL}                                   {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  1. Open {Fore.CYAN}https://gemini.google.com{Style.RESET_ALL} in Chrome/Edge/Brave            {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  2. Press {Fore.WHITE}F12{Style.RESET_ALL} → Application > Cookies                              {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  3. Copy {Fore.YELLOW}__Secure-1PSID{Style.RESET_ALL} and {Fore.YELLOW}__Secure-1PSIDTS{Style.RESET_ALL}                      {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  4. Add to {Fore.WHITE}.env{Style.RESET_ALL}:                                              {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}     $ {{Fore.GREEN}}echo "SECURE_1PSID=your_cookie" >> .env{Style.RESET_ALL}               {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}     $ {{Fore.GREEN}}echo "SECURE_1PSIDTS=your_cookie" >> .env{Style.RESET_ALL}             {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Current status:{Style.RESET_ALL}                                                          {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {'{'}{Fore.GREEN}✓ API key configured{Style.RESET_ALL} if {_has_api_key} else {Fore.YELLOW}✗ No API key{Style.RESET_ALL}{'}'}                       {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {'{'}{Fore.GREEN}✓ Cookies configured{Style.RESET_ALL} if {_has_cookies} else {Fore.YELLOW}✗ No cookies{Style.RESET_ALL}{'}'}                       {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Verify:{Style.RESET_ALL}                                                                 {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}     $ {{Fore.GREEN}}python gemini_bridge.py --health{Style.RESET_ALL}                         {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}╰{'─' * 60}╯{Style.RESET_ALL}
"""
        print(_b)
        if SECURE_1PSID and SECURE_1PSIDTS:
            print(f"  {Fore.GREEN}✓ Credentials found in .env{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}No credentials found yet. Follow the steps above.{Style.RESET_ALL}")
        return
    if _args.show_config:
        try:
            from src.config import AppConfig
            cfg = AppConfig()
            print(f"  {'─' * 50}")
            print(f"  Current Configuration:")
            print(f"  {'─' * 50}")
            for key, value in sorted(cfg.model_dump().items()):
                print(f"    {key}: {value}")
            print(f"  {'─' * 50}")
        except Exception as e:
            print(f"  Error loading config: {e}")
        return

    if not GEMINI_API_KEY and (not SECURE_1PSID or not SECURE_1PSIDTS):
        print(f"{Fore.RED}Error: No credentials found.{Style.RESET_ALL}")
        print(f"  Set GEMINI_API_KEY in .env for API key auth, or")
        print(f"  set SECURE_1PSID + SECURE_1PSIDTS for cookie auth.")
        print(f"  Use {Fore.CYAN}--auth{Style.RESET_ALL} for setup instructions.")
        return


    # Script mode: one-shot query, JSON output, no TUI
    script_mode = _args.script is not None
    script_query = _args.script if _args.script is not None else None

    # Session auto-load: --session <name> loads a saved session on startup
    session_to_load = _args.session

    import time as _startup_time
    _t0 = _startup_time.monotonic()
    telemetry.start_session()
    _t_telemetry = _startup_time.monotonic()
    
    # Crash recovery: detect interrupted sessions
    try:
        _last_end = telemetry._check_last_session_end()
        if _last_end is not None and not _last_end:
            print(f"  {Fore.YELLOW}⚠ Previous session ended abnormally — recovery check available{Style.RESET_ALL}")
            telemetry.log_interaction("system", "Previous session ended abnormally (recovery check)", "status")
    except Exception:
        pass
    
    _t_before_init = _startup_time.monotonic()
    client, chat, chat_context = await initialize_bridge()
    _t_init = _startup_time.monotonic()
    if not client:
        return

    # Initialize ToolExecutor with all dependencies
    _t_executor = _startup_time.monotonic()
    executor = ToolExecutor(
        workspace_root=WORKSPACE_ROOT,
        telemetry=telemetry,
        conversation=conversation,
        permission_mgr=permission_mgr,
        checkpoint_mgr=checkpoint_mgr,
        diff_engine=diff_engine,
        tool_registry=tool_registry,
        verbose_mode=VERBOSE_MODE,
    )
    # Start file watcher for workspace change detection
    file_watcher = FileWatcher(WORKSPACE_ROOT, interval=3.0)
    try:
        fw_task = asyncio.create_task(file_watcher.start())
    except Exception:
        pass
    
    # Initialize prompt template registry
    prompt_registry = create_default_registry(log_dir=telemetry.logs_dir / "prompts")

    # Cross-session cache warming (D2#4)
    try:
        from src.core.cache_manager import CrossSessionWarmer, TTLConfig
        warmer = CrossSessionWarmer(bridge_ctx.memory._cache if hasattr(bridge_ctx.memory, '_cache') else None)
        if warmer.cache:
            session_history = bridge_ctx.memory.get_recent_sessions(limit=5) if hasattr(bridge_ctx.memory, 'get_recent_sessions') else []
            if session_history:
                warmer.warm_from_history(session_history)
                if VERBOSE_MODE:
                    print(f"  [cache] Warmed {len(session_history)} sessions")
    except Exception as warm_err:
        if VERBOSE_MODE:
            print(f"  [cache] Warming skipped: {warm_err}")
    
    # Start periodic memory flush
    flush_task = asyncio.create_task(memory.periodic_flush(interval=5.0))
    
    # Start periodic WAL checkpoint task for SQLite durability
    import sqlite3 as _sqlite3
    
    async def _periodic_wal_checkpoint():
        """Periodically checkpoint WAL files to keep them bounded."""
        _paths_checked = set()
        while True:
            await asyncio.sleep(60)  # Every 60 seconds
            for _db_path in [str(telemetry.db_path), str(memory.db.db_path)]:
                if _db_path in _paths_checked:
                    continue
                try:
                    _conn = _sqlite3.connect(_db_path, timeout=2)
                    _conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    _conn.close()
                    _paths_checked.add(_db_path)
                except Exception:
                    pass
    
    _wal_task = asyncio.create_task(_periodic_wal_checkpoint())
    
    # Auto-load session if --session flag was provided
    if session_to_load:
        save_dir = WORKSPACE_ROOT / ".ww" / "sessions" / session_to_load
        conv_file = save_dir / "conversation.json"
        if conv_file.exists():
            import json as _json
            try:
                conv_data = _json.loads(conv_file.read_text())
                conversation.turns = []
                memory.clear_history()
                for t in conv_data:
                    conversation.add_turn(t["role"], t["content"])
                    memory.add_turn(t["role"], t["content"])
                telemetry.log_interaction("system", f"Session loaded: {session_to_load} ({len(conv_data)} turns)")
                log_status("📂", f"Session loaded", f"{session_to_load} ({len(conv_data)} turns)")
            except Exception as e:
                telemetry.log_interaction("system", f"Failed to load session: {e}", "error")
                log_status("❌", f"Failed to load session", str(e))
        else:
            telemetry.log_interaction("system", f"Session not found: {session_to_load}", "error")
            log_status("❌", f"Session not found", session_to_load)

    # Script mode: run one query, output JSON, exit
    if script_mode and script_query:
        import json as _json
        telemetry.log_interaction("user", script_query)
        conversation.add_turn("user", script_query)
        memory.add_turn("user", script_query)
        BRIDGE_STATUS = "Processing"
        try:
            resp = await safe_send_message(chat, script_query)
            telemetry.log_interaction("communicator", resp.text)
            conversation.add_turn("assistant", resp.text)
            memory.add_turn("assistant", resp.text)
            result = {"status": "ok", "response": resp.text, "turns": len(conversation.turns)}
            print(_json.dumps(result, indent=2))
        except Exception as e:
            result = {"status": "error", "error": str(e), "turns": len(conversation.turns)}
            print(_json.dumps(result, indent=2))
        telemetry.end_session(summary=f"Script mode: {script_query[:80]}")
        return

    from prompt_toolkit.history import FileHistory
    _hist_path = WORKSPACE_ROOT / ".ww" / "history.txt"
    _hist_path.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        style=pt_style,
        key_bindings=kb,
        mouse_support=False,
        history=FileHistory(str(_hist_path)),
        enable_history_search=True,
        complete_while_typing=True,
    )

    # Track task count for progressive disclosure tips
    _task_count = 0

    # Welcome banner on fresh sessions
    if not session_to_load:
        welcome_text = f"""
  {Fore.CYAN}╭{'─' * 60}╮{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Welcome to WW Bridge{Style.RESET_ALL} -- your {Fore.YELLOW}Gemini-powered{Style.RESET_ALL} coding assistant.  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  Try these sample queries:                                        {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {Fore.GREEN}>\"List all Python files in the project\"{Style.RESET_ALL}                         {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {Fore.GREEN}>\"Explain the architecture of this project\"{Style.RESET_ALL}                     {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {Fore.GREEN}>\"Run the test suite\"{Style.RESET_ALL}                                    {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {Fore.GREEN}>\"Find and fix any bugs in the code\"{Style.RESET_ALL}                              {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}    {Fore.GREEN}> /help{Style.RESET_ALL} for all commands                                             {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Session:{Style.RESET_ALL} default  |  {Fore.WHITE}Policy:{Style.RESET_ALL} {permission_mgr.policy.value}  |  {Fore.WHITE}Tools:{Style.RESET_ALL} {len(tool_defs)} registered       {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}                                                                  {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Tip:{Style.RESET_ALL} Type your first query to get started!                                    {Fore.CYAN}│{Style.RESET_ALL}
  {Fore.CYAN}╰{'─' * 60}╯{Style.RESET_ALL}
"""
        print(welcome_text)
    else:
        print(f"  {Fore.CYAN}╭{'─' * 60}╮{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Session loaded:{Style.RESET_ALL} {session_to_load}                                   {Fore.CYAN}│{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}│{Style.RESET_ALL}  {Fore.WHITE}Policy:{Style.RESET_ALL} {permission_mgr.policy.value}  |  {Fore.WHITE}Workspace:{Style.RESET_ALL} {WORKSPACE_ROOT.name}                     {Fore.CYAN}│{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}╰{'─' * 60}╯{Style.RESET_ALL}")

    if _args.profile_startup:
        _t_done = _startup_time.monotonic()
        print(f"  {Fore.CYAN}⏱ Startup profile:{Style.RESET_ALL}")
        print(f"    Telemetry init: {_t_telemetry - _t0:.2f}s")
        print(f"    Bridge init:    {_t_init - _t_before_init:.2f}s")
        print(f"    Tool executor:  {_t_executor - _t_init:.2f}s")
        print(f"    Total startup:  {_t_done - _t0:.2f}s")
    print(f"\n  {Fore.WHITE}Commands: /tokens /undo /compact /reload /init /verbose /policy /history /save /load /sessions /memory /export exit{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Policy: {permission_mgr.policy.value} | Workspace: {WORKSPACE_ROOT}{Style.RESET_ALL}\n")

    while True:
        try:
            # p10k inspired prompt components
            mode_segment = " \uf0c2 GEMINI "
            mode_color = "#58a6ff"
            dir_name = WORKSPACE_ROOT.name
            
            prompt_html = HTML(
                f'<style bg="{mode_color}" fg="#000000">{mode_segment}</style>'
                f'<style bg="#30363d" fg="{mode_color}">\ue0b0</style>'
                f'<style bg="#30363d" fg="#ffffff"> \uf07b {dir_name} </style>'
                f'<style fg="#30363d">\ue0b0</style> '
            )

            user_input = await session.prompt_async(prompt_html, bottom_toolbar=get_bottom_toolbar)
            if not user_input: continue
            
            cmd = user_input.strip()
            if cmd.lower() in ('exit', 'quit'):
                telemetry.end_session(summary="User exited.")
                break

            if cmd.startswith("/"):
                c = cmd.split(" ")[0].lower()
                args = cmd[len(c) + 1:].strip() if " " in cmd else ""
                
                # Try COMMAND_TABLE dispatch first (new modular architecture)
                if c in COMMAND_TABLE:
                    bridge_ctx.verbose_mode = VERBOSE_MODE
                    bridge_ctx.bridge_status = BRIDGE_STATUS
                    bridge_ctx.agent_sessions = AGENT_SESSIONS
                    await COMMAND_TABLE[c](bridge_ctx, args)
                    # Sync mutable state back
                    VERBOSE_MODE = bridge_ctx.verbose_mode
                    BRIDGE_STATUS = bridge_ctx.bridge_status
                    continue
                
                # Fallback to inline handlers for commands that need local scope
                if c == "/reload":
                    log_status("🔄", "Reloading bridge...")
                    AGENT_SESSIONS.clear()
                    client, chat, chat_context = await initialize_bridge()
                    continue
                elif c == "/init":
                    from src.agents_loader import create_default_agents_md
                    path = create_default_agents_md(WORKSPACE_ROOT)
                    log_status("📄", f"Created {path}")
                    continue
                elif c == "/plugins":
                    if not plugin_scanner:
                        print(f"  {Fore.YELLOW}Plugin system not available.{Style.RESET_ALL}")
                        continue
                    if " " in cmd and cmd.split(" ", 1)[1].strip().lower() == "reload":
                        log_status("🔄", "Reloading plugins...")
                        loaded = await plugin_scanner.reload_all(tool_registry)
                        log_status("✅", f"Plugins reloaded: {', '.join(loaded) if loaded else 'none'}")
                    else:
                        print(f"  {Fore.CYAN}Loaded Plugins:{Style.RESET_ALL}")
                        if not plugin_scanner.plugins:
                            print("    None.")
                        for name, plugin in plugin_scanner.plugins.items():
                            print(f"    - {Fore.YELLOW}{name}{Style.RESET_ALL} v{plugin.spec.version}: {plugin.spec.description}")
                        print(f"\n  Use {Fore.WHITE}/plugins reload{Style.RESET_ALL} to hot-reload from disk.")
                    continue
                else:
                    # Unknown command
                    print(f"  Unknown command: /{c}")
                    print(f"  Valid commands: tokens, undo, compact, reload, init, verbose, history, memory, save, load, sessions, export, policy, plugins")
                    continue

            telemetry.log_interaction("user", user_input)
            conversation.add_turn("user", user_input)
            memory.add_turn("user", user_input)
            log_status("⌛", "Waiting")
            try:
                from src.gfx.mascot_tui import Mascot as _Mascot
                _m = _Mascot()
                _m.on_event('THINKING')
            except Exception:
                pass

            # Inject memory context into user message using templates
            memory_ctx = memory.build_context()
            memory_prefix = ""
            for c in memory_ctx:
                if c['role'] == 'system' and c.get('content', '').strip():
                    memory_prefix += c['content'] + "\n\n"
            
            # Use prompt templates for structured construction
            try:
                if memory_prefix.strip():
                    augmented_input = prompt_registry.render(
                        "user_query_with_context",
                        memory_context=memory_prefix.strip() + "\n\n",
                        user_input=user_input,
                    )
                else:
                    augmented_input = prompt_registry.render(
                        "user_query",
                        memory_context="",
                        user_input=user_input,
                    )
            except Exception:
                # Fallback to direct construction if template fails
                augmented_input = user_input
                if memory_prefix.strip():
                    augmented_input = f"[PERSISTENT CONTEXT]\n{memory_prefix.strip()}\n\n[USER QUERY]\n{user_input}"
            
            # Live progress tracking
            import time as _time
            _progress_start = _time.monotonic()
            BRIDGE_STATUS = "Processing"
            
            response = await safe_send_message(chat, augmented_input)
            telemetry.log_interaction("communicator", response.text)
            conversation.add_turn("assistant", response.text)
            memory.add_turn("assistant", response.text)
            
            _elapsed = _time.monotonic() - _progress_start
            _status_emoji = "✅" if response and response.text else "⚠️"
            # Overwrite progress line
            print(f"  \r{' ' * 60}\r{_status_emoji} [⏱ {_elapsed:.1f}s] Response received\n")
            print(f"\n{response.text}\n")
            try:
                from src.gfx.mascot_tui import Mascot as _Mascot
                _m = _Mascot()
                _m.on_event('SUCCESS')
            except Exception:
                pass
            await executor.execute(response.text, chat_context, safe_send_message)
            
            # Progressive disclosure tips based on task count
            _task_count += 1
            if _task_count == 3:
                print(f"  {Fore.MAGENTA}💡 Tip: Try /memory to see your session's 3-tier context.{Style.RESET_ALL}")
            elif _task_count == 5:
                print(f"  {Fore.MAGENTA}💡 Tip: Try /save to bookmark your session and /sessions to list them.{Style.RESET_ALL}")
            elif _task_count == 10:
                print(f"  {Fore.MAGENTA}💡 Tip: Try /export to save this session as Markdown for sharing.{Style.RESET_ALL}")
            elif _task_count == 15:
                print(f"  {Fore.MAGENTA}💡 Tip: Use /policy to change approval mode (always/on-request/never).{Style.RESET_ALL}")
            elif _task_count == 25:
                print(f"  {Fore.MAGENTA}💡 Tip: You've completed {_task_count} tasks! Try /plugins to explore extensions.{Style.RESET_ALL}")

        except KeyboardInterrupt: continue
        except EOFError: break
        except Exception as e:
            from src.utils.validation import format_error
            formatted = format_error(e, verbose=VERBOSE_MODE)
            for line in formatted.split("\n"):
                print(f"  {Fore.RED}{line.strip()}{Style.RESET_ALL}")
            try:
                from src.gfx.mascot_tui import Mascot as _Mascot
                _m = _Mascot()
                _m.on_event('ERROR')
            except Exception:
                pass
            telemetry.log_interaction("system", f"Runtime Error: {e}", "error")

if __name__ == "__main__":
    asyncio.run(main())
