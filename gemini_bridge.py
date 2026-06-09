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
import datetime
import traceback
from pathlib import Path
from dotenv import load_dotenv
from gemini_webapi import GeminiClient
from smart_context import get_workspace_context, read_file_surgical, get_directory_context
from context_manager import ConversationHistory, RepoMapper, TokenCounter
from permissions import PermissionManager, ApprovalPolicy, PermissionLevel
from diff_engine import DiffEngine
from checkpoint import CheckpointManager
from agents_loader import load_all_instructions
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

# Load environment variables from .env file
load_dotenv()

SECURE_1PSID = os.getenv("SECURE_1PSID")
SECURE_1PSIDTS = os.getenv("SECURE_1PSIDTS")

# Workspace root - auto-detect from CWD or explicit path
WORKSPACE_ROOT = Path(os.getenv("WW_WORKSPACE", ".")).resolve()

# --- Core Systems ---
conversation = ConversationHistory(context_window=128_000)
token_counter = TokenCounter()
checkpoint_mgr = CheckpointManager(WORKSPACE_ROOT)
permission_mgr = PermissionManager(WORKSPACE_ROOT, ApprovalPolicy.ON_REQUEST)
diff_engine = DiffEngine()

VERBOSE_MODE = False
BRIDGE_STATUS = "Idle"
AGENT_SESSIONS = {}  # Persistent sub-agent chat objects


def get_compact_time():
    return datetime.datetime.now().strftime("%H:%M:%S")


def log_status(emoji, title, detail=""):
    """Print a timestamped status line."""
    timestamp = f"{Fore.WHITE}[{get_compact_time()}]{Style.RESET_ALL}"
    title_str = f"{Fore.CYAN}{title}{Style.RESET_ALL}"
    detail_str = f" {Fore.WHITE}{detail}{Style.RESET_ALL}" if detail else ""
    print(f"  {timestamp} {emoji} {title_str}{detail_str}")


def print_header():
    """Print the startup banner."""
    banner = f"""
{Fore.CYAN}╭─────────────────────────────────────────────╮
│  {Fore.WHITE}WW NEURAL BRIDGE{Fore.CYAN} - Frontier Harness v3.0   │
│  {Fore.WHITE}Context: Token-aware │ Edits: Fuzzy-match{Fore.CYAN}  │
│  {Fore.WHITE}Safety: Sandboxed    │ State: Checkpointed{Fore.CYAN} │
╰─────────────────────────────────────────────╯{Style.RESET_ALL}
"""
    print(banner)


def print_token_bar():
    """Display the current token utilization bar."""
    report = conversation.get_token_report()
    print(f"  {Fore.YELLOW}{report}{Style.RESET_ALL}")


class ToolExecutor:
    """
    Executes tool blocks emitted by the LLM.

    Implements:
    - Path sandboxing (all operations confined to WORKSPACE_ROOT)
    - Permission checks (dangerous commands require approval)
    - Checkpoint creation before destructive operations
    - Fuzzy matching for SEARCH/REPLACE edits
    - Colorized diff output for all file modifications
    """

    @staticmethod
    def parse_fields(content: str) -> dict:
        """Parse key:value fields from tool block content."""
        fields = {}
        lines = content.splitlines()
        current_key = None
        current_value = []
        known_keys = {
            "agent", "task", "filepath", "content",
            "find", "replace", "pattern", "path", "depth"
        }

        for line in lines:
            found_key = False
            for k in known_keys:
                if line.lower().startswith(f"{k}:"):
                    if current_key:
                        fields[current_key] = "\n".join(current_value).strip()
                    current_key = k
                    current_value = [line[len(k) + 1:].strip()]
                    found_key = True
                    break
            if not found_key:
                if current_key:
                    current_value.append(line)

        if current_key:
            fields[current_key] = "\n".join(current_value).strip()
        return fields

    @staticmethod
    def is_safe_path(path: str) -> bool:
        """Validate that a path is within the workspace boundary."""
        try:
            abs_path = Path(path).resolve()
            return str(abs_path).startswith(str(WORKSPACE_ROOT))
        except Exception:
            return False

    @staticmethod
    async def execute(response_text, chat_context):
        """
        Parse and execute all tool blocks in a response.

        Returns True if any tools were executed.
        """
        blocks = re.findall(r"```tool:(\w+)\s*\n?(.*?)\n?```", response_text, re.DOTALL)
        if not blocks:
            return False

        agents_dir = WORKSPACE_ROOT / "agents"
        known_agents = [
            f.stem.lower() for f in agents_dir.glob("*.md")
        ] if agents_dir.exists() else []

        for tool, content in blocks:
            log_status("🛠️", f"TOOL: {tool.upper()}")
            tool_output = ""

            try:
                # --- DELEGATION ---
                if tool == "delegate" or tool.lower() in known_agents:
                    tool_output = await ToolExecutor._handle_delegate(
                        tool, content, chat_context, known_agents
                    )

                # --- FILE READ ---
                elif tool == "read":
                    tool_output = ToolExecutor._handle_read(content)

                # --- DIRECTORY FOCUS ---
                elif tool == "focus":
                    tool_output = ToolExecutor._handle_focus(content)

                # --- FILE WRITE ---
                elif tool == "write":
                    tool_output = await ToolExecutor._handle_write(content)

                # --- SHELL COMMAND ---
                elif tool == "shell":
                    tool_output = await ToolExecutor._handle_shell(content)

                # --- DIRECTORY LIST ---
                elif tool == "list":
                    tool_output = ToolExecutor._handle_list(content)

                # --- SEARCH ---
                elif tool == "search":
                    tool_output = await ToolExecutor._handle_search(content)

                # --- REPLACE (FUZZY) ---
                elif tool == "replace":
                    tool_output = await ToolExecutor._handle_replace(content)

                else:
                    tool_output = f"ERROR: Unknown tool '{tool}'."

            except Exception as e:
                tool_output = f"CRITICAL TOOL ERROR: {type(e).__name__}: {e}"
                if VERBOSE_MODE:
                    traceback.print_exc()

            # Feed tool output back to the LLM
            if tool_output:
                log_status("📡", "Feedback", f"{len(tool_output)} chars")
                conversation.add_turn("tool", tool_output, tool_output=True)

                # Check for compaction need
                if conversation.needs_compaction():
                    log_status("🗜️", "Auto-compacting context window")
                    result = conversation.compact()
                    if VERBOSE_MODE:
                        print(f"  {Fore.YELLOW}{result}{Style.RESET_ALL}")

                feedback_msg = f"TOOL_OUTPUT ({tool.upper()}):\n{tool_output}"
                response = await safe_send_message(chat_context['chat'], feedback_msg)
                conversation.add_turn("assistant", response.text)

                if VERBOSE_MODE:
                    print(f"  {Fore.WHITE}[Feedback Response]: {response.text[:200]}...{Style.RESET_ALL}")

                # Recursively execute any tools in the feedback response
                await ToolExecutor.execute(response.text, chat_context)

        return True

    @staticmethod
    async def _handle_delegate(tool, content, chat_context, known_agents):
        """Handle agent delegation."""
        fields = ToolExecutor.parse_fields(content)
        agent_name = (
            tool.lower() if tool.lower() in known_agents
            else fields.get("agent", "").lower()
        )
        task = fields.get("task", "") if "task" in fields else content.strip()

        if not agent_name or not task:
            return "ERROR: Missing agent or task for delegation."

        log_status("↗️", f"Delegating to {agent_name.upper()}")

        # Get or create persistent session
        if agent_name not in AGENT_SESSIONS:
            spec_path = WORKSPACE_ROOT / "agents" / f"{agent_name}.md"
            if not spec_path.exists():
                spec_path = WORKSPACE_ROOT / "agents" / "specialized.md"

            spec_text = (
                spec_path.read_text() if spec_path.exists()
                else f"You are the {agent_name.upper()} AGENT."
            )
            sub_chat = chat_context['client'].start_chat()
            base_instructions = ""
            base_path = WORKSPACE_ROOT / "GEM_INSTRUCTIONS.md"
            if base_path.exists():
                base_instructions = base_path.read_text()

            priming = (
                f"SYSTEM INSTRUCTIONS:\n{spec_text}\n\n"
                f"TOOL PROTOCOLS:\n{base_instructions}\n\n"
                "INITIALIZATION: Start session. Execute tasks immediately using tool blocks."
            )
            await safe_send_message(sub_chat, priming)
            AGENT_SESSIONS[agent_name] = sub_chat

        sub_chat = AGENT_SESSIONS[agent_name]
        sub_response = await safe_send_message(sub_chat, f"TASK: {task}")

        # Process sub-agent tools recursively
        await ToolExecutor.execute(
            sub_response.text,
            {'client': chat_context['client'], 'chat': sub_chat}
        )

        log_status("↙️", f"{agent_name.upper()} complete")
        return (
            f"AGENT {agent_name.upper()} completed task.\n"
            f"Response: {sub_response.text}"
        )

    @staticmethod
    def _handle_read(content):
        """Handle file read with sandboxing and truncation."""
        path = content.strip()
        if not ToolExecutor.is_safe_path(path):
            return "ERROR: Path outside workspace boundary."

        file_path = Path(path)
        if not file_path.exists():
            return f"ERROR: File '{path}' not found."

        return read_file_surgical(file_path, max_lines=500)

    @staticmethod
    def _handle_focus(content):
        """Handle deep directory context."""
        fields = ToolExecutor.parse_fields(content)
        path = fields.get("path", ".").strip()
        depth = int(fields.get("depth", "2"))

        if not ToolExecutor.is_safe_path(path):
            return "ERROR: Path outside workspace boundary."

        return get_directory_context(Path(path), depth=depth)

    @staticmethod
    async def _handle_write(content):
        """Handle file write with checkpointing and permission checks."""
        fields = ToolExecutor.parse_fields(content)
        filepath = fields.get("filepath")
        file_content = fields.get("content")

        if not filepath or file_content is None:
            return "ERROR: Missing filepath or content for write."
        if not ToolExecutor.is_safe_path(filepath):
            return "ERROR: Path outside workspace boundary."

        # Permission check
        perm = permission_mgr.classify_write(filepath)
        if perm == PermissionLevel.DENY:
            return f"DENIED: Cannot write to protected path '{filepath}'."
        if perm == PermissionLevel.ASK:
            response = await permission_mgr.request_approval(
                f"Write file: {filepath}"
            )
            if response == "n":
                return "DENIED: User rejected file write."

        # Create checkpoint before writing
        file_path = Path(filepath)
        cp_id = checkpoint_mgr.create_checkpoint(f"write:{filepath}")
        if file_path.exists():
            checkpoint_mgr.save_file_state(file_path, cp_id)

        # Capture old content for diff
        old_content = file_path.read_text() if file_path.exists() else ""

        # Write the file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_content)

        # Show diff
        if old_content:
            diff = DiffEngine.colorize_diff(old_content, file_content, filepath)
            if diff:
                print(diff)

        log_status("✅", f"Wrote {filepath}")
        return f"SUCCESS: Wrote to {filepath} ({len(file_content)} chars)"

    @staticmethod
    async def _handle_shell(content):
        """Handle shell command with permission checks and timeout."""
        cmd = content.strip()
        if not cmd:
            return "ERROR: Empty shell command."

        # Permission check
        perm = permission_mgr.classify_command(cmd)
        if perm == PermissionLevel.DENY:
            return f"DENIED: Command '{cmd}' is not allowed."
        if perm == PermissionLevel.ASK:
            response = await permission_mgr.request_approval(f"Run command: {cmd}")
            if response == "n":
                return "DENIED: User rejected command execution."
            elif response == "a":
                permission_mgr.always_allow.add(cmd)

        log_status("🐚", f"$ {cmd[:60]}{'...' if len(cmd) > 60 else ''}")

        try:
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=60
            )
            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += f"\nSTDERR: {stderr.decode(errors='replace')}"
            if process.returncode != 0:
                output += f"\n[Exit code: {process.returncode}]"

            # Truncate very long outputs
            if len(output) > 10000:
                output = (
                    output[:4000]
                    + f"\n\n[... {len(output) - 8000} chars truncated ...]\n\n"
                    + output[-4000:]
                )

            return output or "(no output)"

        except asyncio.TimeoutError:
            return "ERROR: Command timed out after 60 seconds."
        except Exception as e:
            return f"ERROR: Shell execution failed: {e}"

    @staticmethod
    def _handle_list(content):
        """Handle directory listing."""
        path = content.strip() or "."
        if not ToolExecutor.is_safe_path(path):
            return "ERROR: Path outside workspace boundary."

        try:
            files = os.listdir(path)
            entries = []
            for f in sorted(files):
                full = os.path.join(path, f)
                suffix = "/" if os.path.isdir(full) else ""
                entries.append(f"{f}{suffix}")
            return "\n".join(entries) or "(empty directory)"
        except Exception as e:
            return f"ERROR: {e}"

    @staticmethod
    async def _handle_search(content):
        """Handle file/content search."""
        fields = ToolExecutor.parse_fields(content)
        pattern = fields.get("pattern", "")
        search_path = fields.get("path", ".")

        if not pattern:
            return "ERROR: No search pattern provided."
        if not ToolExecutor.is_safe_path(search_path):
            return "ERROR: Path outside workspace boundary."

        cmd = (
            f"find {search_path} -maxdepth 4 -name '*{pattern}*' 2>/dev/null; "
            f"grep -rli '{pattern}' {search_path} --include='*.py' "
            f"--include='*.js' --include='*.ts' --include='*.md' "
            f"--include='*.json' --include='*.yaml' --include='*.yml' "
            f"2>/dev/null | head -n 30"
        )

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE_ROOT),
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode(errors="replace") if stdout else ""
        return output or f"No results found for '{pattern}'."

    @staticmethod
    async def _handle_replace(content):
        """Handle fuzzy SEARCH/REPLACE with diff display."""
        fields = ToolExecutor.parse_fields(content)
        filepath = fields.get("filepath")

        if not filepath:
            return "ERROR: Missing filepath for replace."
        if not ToolExecutor.is_safe_path(filepath):
            return "ERROR: Path outside workspace boundary."

        file_path = Path(filepath)
        if not file_path.exists():
            return f"ERROR: File '{filepath}' not found."

        # Parse SEARCH/REPLACE blocks (Aider-style)
        find_content = fields.get("find", "")
        replace_content = fields.get("replace", "")

        # Check for <<<<<<< SEARCH / ======= / >>>>>>> REPLACE format
        search_match = re.search(
            r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE",
            find_content,
            re.DOTALL,
        )
        if search_match:
            find_content = search_match.group(1)
            replace_content = search_match.group(2)

        if not find_content:
            return "ERROR: Empty search block."

        # Create checkpoint before editing
        cp_id = checkpoint_mgr.create_checkpoint(f"replace:{filepath}")
        checkpoint_mgr.save_file_state(file_path, cp_id)

        # Apply fuzzy edit
        success, message, diff_output = diff_engine.apply_edit(
            file_path, find_content, replace_content
        )

        if success and diff_output:
            print(diff_output)

        status_emoji = "✅" if success else "❌"
        log_status(status_emoji, message)
        return message


async def safe_send_message(chat, message, max_retries=3):
    """Send a message with exponential backoff retry."""
    global BRIDGE_STATUS
    BRIDGE_STATUS = "Processing"

    if VERBOSE_MODE:
        tokens = token_counter.count(message)
        print(f"  {Fore.WHITE}[DEBUG] Sending {tokens} tokens...{Style.RESET_ALL}")

    for attempt in range(max_retries):
        try:
            result = await chat.send_message(message)
            BRIDGE_STATUS = "Active"
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
                raise e

            await asyncio.sleep(wait)


async def initialize_bridge():
    """Initialize the Gemini client and prime the main conversation."""
    global BRIDGE_STATUS
    BRIDGE_STATUS = "Initializing"
    log_status("⚙️", "Initializing Gemini client...")

    client = GeminiClient(SECURE_1PSID, SECURE_1PSIDTS)
    try:
        await client.init(timeout=45, auto_refresh=True)
        log_status("✅", "Client initialized")
    except Exception as e:
        log_status("❌", "Init failed", str(e))
        BRIDGE_STATUS = "Error"
        return None, None, None

    chat = client.start_chat()

    # Load instructions from AGENTS.md hierarchy
    agents_instructions = load_all_instructions(WORKSPACE_ROOT)

    # Load agent registry
    agents_dir = WORKSPACE_ROOT / "agents"
    agent_specs = []
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            content = agent_file.read_text()
            if content.strip():
                agent_specs.append(
                    f"### AGENT: {agent_file.stem.upper()}\n{content}"
                )

    agent_registry = "\n\n".join(agent_specs)

    # Load base tool instructions
    base_instructions = ""
    base_path = WORKSPACE_ROOT / "GEM_INSTRUCTIONS.md"
    if base_path.exists():
        base_instructions = base_path.read_text()

    # Gather workspace context (includes repo map)
    log_status("📊", "Gathering workspace context...")
    workspace_context = get_workspace_context(str(WORKSPACE_ROOT))

    # Build the priming message
    comm_path = WORKSPACE_ROOT / "agents" / "communicator.md"
    comm_instructions = comm_path.read_text() if comm_path.exists() else ""

    priming_message = (
        f"YOUR IDENTITY:\n{comm_instructions}\n\n"
        f"PROJECT INSTRUCTIONS (AGENTS.md):\n{agents_instructions}\n\n"
        f"AGENT REGISTRY:\n{agent_registry}\n\n"
        f"BASE TOOL PROTOCOLS:\n{base_instructions}\n\n"
        f"WORKSPACE CONTEXT:\n{workspace_context}\n\n"
        "Acknowledge your role. To summon agents or use tools, emit the tool blocks. "
        "Outputs will be fed back automatically."
    )

    # Track token usage
    priming_tokens = token_counter.count(priming_message)
    conversation.set_system_prompt_tokens(priming_tokens)
    log_status("📐", f"System prompt: {priming_tokens:,} tokens")

    log_status("🚀", "Priming conversation...")
    await safe_send_message(chat, priming_message)
    BRIDGE_STATUS = "Active"

    return client, chat, {'client': client, 'chat': chat}


async def main():
    """Main event loop with command handling."""
    global VERBOSE_MODE, BRIDGE_STATUS

    if "--verbose" in sys.argv:
        VERBOSE_MODE = True
        sys.argv.remove("--verbose")

    print_header()

    if not SECURE_1PSID or not SECURE_1PSIDTS:
        print(f"{Fore.RED}Error: SECURE_1PSID and SECURE_1PSIDTS must be set in .env{Style.RESET_ALL}")
        return

    client, chat, chat_context = await initialize_bridge()
    if not client:
        return

    print_token_bar()
    print(f"\n  {Fore.WHITE}Commands: /tokens /undo /compact /reload /init /verbose exit{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}Policy: {permission_mgr.policy.value} | Workspace: {WORKSPACE_ROOT}{Style.RESET_ALL}\n")

    while True:
        try:
            # Use simple input (prompt_toolkit optional)
            try:
                user_input = input(f"{Fore.GREEN}ww>{Style.RESET_ALL} ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            cmd = user_input.lower()

            # --- Built-in Commands ---
            if cmd in ('exit', 'quit'):
                log_status("👋", "Session ended")
                break

            elif cmd == "/tokens":
                print_token_bar()
                continue

            elif cmd == "/undo":
                result = checkpoint_mgr.undo()
                log_status("↩️", result)
                continue

            elif cmd == "/compact":
                result = conversation.compact()
                log_status("🗜️", result)
                print_token_bar()
                continue

            elif cmd == "/reload":
                log_status("🔄", "Reloading bridge...")
                AGENT_SESSIONS.clear()
                client, chat, chat_context = await initialize_bridge()
                if client:
                    print_token_bar()
                continue

            elif cmd == "/init":
                from agents_loader import create_default_agents_md
                path = create_default_agents_md(WORKSPACE_ROOT)
                log_status("📄", f"Created {path}")
                continue

            elif cmd == "/verbose":
                VERBOSE_MODE = not VERBOSE_MODE
                log_status("🔧", f"Verbose mode: {'ON' if VERBOSE_MODE else 'OFF'}")
                continue

            elif cmd == "/history":
                result = checkpoint_mgr.get_history_summary()
                print(f"  {result}")
                continue

            elif cmd.startswith("/policy "):
                new_policy = cmd.split(" ", 1)[1].strip()
                try:
                    permission_mgr.policy = ApprovalPolicy(new_policy)
                    log_status("🔒", f"Policy set to: {new_policy}")
                except ValueError:
                    print(f"  Valid policies: always, on-request, never")
                continue

            # --- Send to LLM ---
            conversation.add_turn("user", user_input)
            log_status("⌛", "Processing...")

            response = await safe_send_message(chat, user_input)
            conversation.add_turn("assistant", response.text)

            # Display response
            print(f"\n{response.text}\n")

            # Execute any tool blocks
            await ToolExecutor.execute(response.text, chat_context)

            # Auto-compact if needed
            if conversation.needs_compaction():
                log_status("🗜️", "Auto-compacting...")
                result = conversation.compact()
                if VERBOSE_MODE:
                    print(f"  {Fore.YELLOW}{result}{Style.RESET_ALL}")

        except KeyboardInterrupt:
            print(f"\n  {Fore.YELLOW}(Ctrl+C to interrupt, type 'exit' to quit){Style.RESET_ALL}")
            continue
        except Exception as e:
            log_status("❌", f"Error: {e}")
            if VERBOSE_MODE:
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
