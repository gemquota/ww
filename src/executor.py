"""
Tool Executor — extracted from gemini_bridge.py for modularity.

Handles parsing LLM tool blocks (```tool:<name>```) and dispatching
to the appropriate handler or ToolRegistry entry.
"""

import asyncio
import itertools
import os
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from colorama import Fore, Style
from loguru import logger

from src.core.context import read_file_surgical, get_directory_context
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from typing import TYPE_CHECKING
from src.tools.registry import ToolRegistry
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.security import PermissionManager, PermissionLevel, Sandbox
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.diff_engine import DiffEngine
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.checkpoint import CheckpointManager
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.observability import TelemetryManager
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.core.context import ConversationHistory
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager
from src.core.utils.validation import format_error
from src.core.patterns.decision_tracer import DecisionTracer
from src.core.patterns.fault_injector import FaultInjector, should_fail
from src.core.backpressure import BackpressureManager

def log_status(emoji: str, title: str, detail: str = "", telemetry: Optional[TelemetryManager] = None) -> None:
    """Utility for status logging during tool execution."""
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    t_str = f"{Fore.WHITE}[{timestamp}]{Style.RESET_ALL}"
    title_str = f"{Fore.CYAN}{title}{Style.RESET_ALL}"
    detail_str = f" {Fore.WHITE}{detail}{Style.RESET_ALL}" if detail else ""
    print(f"  {t_str} {emoji} {title_str}{detail_str}")
    if telemetry:
        telemetry.log_interaction("system", f"{emoji} {title}: {detail}", "status")

_DEFAULT_MAX_CONCURRENCY = 8  # DAG backpressure semaphore limit

if TYPE_CHECKING:
    from src.ui import UIAdapter
    from src.core.context import BridgeContext
class ToolExecutor:
    """Parses and dispatches tool blocks with causal tracking."""

    @property
    def causal_graph(self):
        """Get CausalGraph from bridge context if available."""
        ctx = getattr(self, 'ctx', None)
        if ctx:
            return getattr(ctx, 'causal_graph', None)
        return None
    """Parses and dispatches tool blocks from LLM responses."""

    KNOWN_KEYS = {
        "agent", "task", "filepath", "content",
        "find", "replace", "pattern", "path", "depth",
    }

    # Default per-tool execution timeout in seconds
    TOOL_TIMEOUT = 120  # Can be overridden per tool via config

    # Tool-specific timeout overrides (tool_name: seconds)
    TOOL_TIMEOUTS = {
        "shell_exec": 300,
        "url_fetch": 60,
        "git_tool": 120,
        "read_file": 30,
        "write_file": 30,
        "file_patch": 30,
        "code_search": 30,
        "list_dir": 15,
        "doc_search": 30,
        "request_clarification": 30,
    }

    TOOL_NAME_MAP = {
        "read": "read_file", "write": "write_file",
        "shell": "shell_exec", "list": "list_dir",
        "search": "code_search", "replace": "file_patch",
        "fetch": "url_fetch", "doc": "doc_search",
        "clarify": "request_clarification",
    }

    def __init__(
        self,
        workspace_root: Path,
        telemetry: TelemetryManager,
        conversation: ConversationHistory,
        permission_mgr: PermissionManager,
        checkpoint_mgr: CheckpointManager,
        diff_engine: DiffEngine,
        tool_registry: ToolRegistry,
        verbose_mode: bool = False,
        ui_adapter: Optional['UIAdapter'] = None,
        ctx: Optional['BridgeContext'] = None,
        max_concurrency: int = _DEFAULT_MAX_CONCURRENCY,
    ):
        # If a BridgeContext is provided, extract values from it
        if ctx is not None:
            workspace_root = workspace_root or ctx.workspace_root
            telemetry = telemetry or ctx.telemetry
            conversation = conversation or ctx.conversation
            permission_mgr = permission_mgr or ctx.permission_mgr
            checkpoint_mgr = checkpoint_mgr or ctx.checkpoint_mgr
            diff_engine = diff_engine or ctx.diff_engine
            tool_registry = tool_registry or ctx.tool_registry
            verbose_mode = verbose_mode or ctx.verbose_mode
            ui_adapter = ui_adapter or getattr(ctx, 'ui_adapter', None)
        self.workspace_root = workspace_root
        self.telemetry = telemetry
        self.conversation = conversation
        self.permission_mgr = permission_mgr
        self.checkpoint_mgr = checkpoint_mgr
        self.diff_engine = diff_engine
        self.tool_registry = tool_registry
        self.verbose_mode = verbose_mode
        self.ctx = ctx
        self.agent_sessions: Dict[str, Any] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self.max_concurrency = max_concurrency
        self.prompt_registry = create_default_registry()

    # ── Public entry point ──────────────────────────────────────────

    async def execute(
        self,
        response_text: str,
        chat_context: Dict[str, Any],
        safe_send_message: callable,
    ) -> bool:
        """Parse tool blocks from response_text and dispatch each."""
        blocks = re.findall(
            r"```tool:(\w+)\s*\n?(.*?)\n?```", response_text, re.DOTALL
        )
        if not blocks:
            return False

        agents_dir = self.workspace_root / "agents"
        known_agents = (
            [f.stem.lower() for f in agents_dir.glob("*.md")]
            if agents_dir.exists()
            else []
        )

        # Fast path for read-only tools: dispatch without semaphore or registry
        _READONLY_FAST = {"read", "read_file", "list", "list_dir", "search", "code_search", "doc_search"}
        
        # Parallel dispatch for multiple independent read-only tools
        if len(blocks) > 1:
            ro_blocks = [(t, c) for t, c in blocks if t in _READONLY_FAST]
            if len(ro_blocks) > 1:
                log_status("⚡", f"Parallel: {len(ro_blocks)} read-only tools", telemetry=self.telemetry)
                async def _run_ro(tool: str, content: str) -> str:
                    registry_name = self.TOOL_NAME_MAP.get(tool, tool)
                    if registry_name not in self.tool_registry.tools:
                        return ""
                    fields = self._parse_fields(content)
                    if registry_name == "read_file" and "read" not in fields:
                        fields = {"file_path": content.strip()}
                    elif registry_name == "list_dir" and "list" not in fields:
                        fields = {"dir_path": content.strip() or "."}
                    fields["permission_mgr"] = self.permission_mgr
                    node = self.tool_registry.tools[registry_name]
                    import inspect
                    sig = inspect.signature(node.func)
                    final_args = {k: v for k, v in fields.items() if k in sig.parameters}
                    async with self._semaphore:
                        return str(await self.tool_registry.execute(registry_name, final_args))
                results = await asyncio.gather(*[_run_ro(t, c) for t, c in ro_blocks])
                for (tool, content), result in zip(ro_blocks, results):
                    log_status("🛠️", f"TOOL: {tool.upper()}", telemetry=self.telemetry)
                    await self._process_tool_output(result, tool, chat_context, safe_send_message)
                # Remove processed tools from blocks
                ro_set = set(ro_blocks)
                remaining = [(t, c) for t, c in blocks if (t, c) not in ro_set]
                if not remaining:
                    return True
                blocks = remaining
                log_status("➡️", f"Sequential: {len(remaining)} tools", telemetry=self.telemetry)
        
        for tool, content in blocks:
            log_status("🛠️", f"TOOL: {tool.upper()}", telemetry=self.telemetry)
            tool_output = ""

            try:
                # Fast path for read-only tools
                if tool in _READONLY_FAST:
                    registry_name = self.TOOL_NAME_MAP.get(tool, tool)
                    if registry_name in self.tool_registry.tools:
                        fields = self._parse_fields(content)
                        if registry_name == "read_file" and "read" not in fields:
                            fields = {"file_path": content.strip()}
                        elif registry_name == "list_dir" and "list" not in fields:
                            fields = {"dir_path": content.strip() or "."}
                        fields["permission_mgr"] = self.permission_mgr
                        node = self.tool_registry.tools[registry_name]
                        import inspect
                        sig = inspect.signature(node.func)
                        final_args = {k: v for k, v in fields.items() if k in sig.parameters}
                        # Causal: record tool execution start
                        causal = getattr(self, 'causal_graph', None)
                        causal_parent = None
                        if causal:
                            ev = causal.create_event(
                                event_type="tool_call",
                                tool_name=registry_name,
                                summary=f"Fast path: {registry_name}",
                                data={"args": {k: str(v)[:100] for k, v in final_args.items() if k != 'permission_mgr'}},
                            )
                            causal_parent = ev.event_id
                        result = await self.tool_registry.execute(registry_name, final_args)
                        tool_output = str(result)
                        if causal and causal_parent:
                            causal.create_event(
                                event_type="tool_result",
                                parent_ids=[causal_parent],
                                tool_name=registry_name,
                                summary=f"Result: {result[:100] if result else 'empty'}",
                            )
                        await self._process_tool_output(tool_output, tool, chat_context, safe_send_message)
                        continue
                
                if tool == "delegate" or tool.lower() in known_agents:
                    tool_output = await self._handle_delegate(
                        tool, content, chat_context, known_agents, safe_send_message,
                    )
                else:
                    # Registry-first dispatch
                    registry_name = self.TOOL_NAME_MAP.get(tool, tool)
                    if registry_name in self.tool_registry.tools:
                        fields = self._parse_fields(content)
                        
                        # Inconsistent field naming fix for registry compatibility
                        if registry_name == "read_file" and "read" not in fields:
                            fields = {"file_path": content.strip()}
                        elif registry_name == "list_dir" and "list" not in fields:
                            fields = {"dir_path": content.strip() or "."}
                        elif registry_name == "write_file":
                            if "filepath" in fields: fields["file_path"] = fields.pop("filepath")
                        elif registry_name == "file_patch":
                            if "filepath" in fields: fields["file_path"] = fields.pop("filepath")
                            if "find" in fields: fields["search_text"] = fields.pop("find")
                            if "replace" in fields: fields["replace_text"] = fields.pop("replace")
                        elif registry_name == "shell_exec":
                            if "command" not in fields: fields = {"command": content.strip()}
                        elif registry_name == "code_search":
                            if "pattern" not in fields: fields = {"pattern": content.strip()}

                        # Inject managers for tools that need them
                        fields["permission_mgr"] = self.permission_mgr
                        fields["checkpoint_mgr"] = self.checkpoint_mgr
                        fields["diff_engine"] = self.diff_engine

                        # Clean up fields to only include those in the tool's signature
                        node = self.tool_registry.tools[registry_name]
                        import inspect
                        sig = inspect.signature(node.func)
                        final_args = {k: v for k, v in fields.items() if k in sig.parameters}

                        # PCG: Add node for tool call
                        tool_node_id = -1
                        if hasattr(chat_context.get("memory"), "graph"):
                            try:
                                tool_node_id = chat_context["memory"].graph.add_node(
                                    event_id=len(self.conversation.turns),
                                    label=f"TOOL_CALL: {registry_name}"
                                )
                            except Exception: pass

                        timeout = self.TOOL_TIMEOUTS.get(registry_name, self.TOOL_TIMEOUT)
                        # Causal: record tool execution
                        causal = getattr(self, 'causal_graph', None)
                        causal_parent = None
                        if causal:
                            ev = causal.create_event(
                                event_type="tool_call",
                                tool_name=registry_name,
                                summary=f"Executing: {registry_name}",
                                data={"args": {k: str(v)[:100] for k, v in final_args.items() if k != 'permission_mgr'}},
                            )
                            causal_parent = ev.event_id
                        try:
                            async with self._semaphore:
                                result = await asyncio.wait_for(
                                    self.tool_registry.execute(registry_name, final_args),
                                    timeout=timeout
                                )
                        except asyncio.TimeoutError:
                            result = f"TOOL TIMEOUT ({registry_name}): exceeded {timeout}s limit"
                            causal.create_event(
                                event_type="tool_timeout",
                                parent_ids=[causal_parent] if causal_parent else None,
                                tool_name=registry_name,
                                summary=f"Timeout after {timeout}s",
                            ) if causal else None
                            logger.warning(f"Tool {registry_name} timed out after {timeout}s")
                        except Exception as e:
                            if causal:
                                causal.create_event(
                                    event_type="tool_error",
                                    parent_ids=[causal_parent] if causal_parent else None,
                                    tool_name=registry_name,
                                    summary=f"Error: {str(e)[:100]}",
                                )
                            raise
                        else:
                            if causal:
                                causal.create_event(
                                    event_type="tool_result",
                                    parent_ids=[causal_parent] if causal_parent else None,
                                    tool_name=registry_name,
                                    summary=f"OK: {str(result)[:100] if result else 'empty'}",
                                )
                        tool_output = str(result)

                        # PCG: Add node for tool output and link to call
                        if tool_node_id != -1:
                            try:
                                out_node_id = chat_context["memory"].graph.add_node(
                                    event_id=len(self.conversation.turns) + 1,
                                    label=f"TOOL_OUTPUT: {registry_name}"
                                )
                                chat_context["memory"].graph.add_edge(
                                    source_id=tool_node_id,
                                    target_id=out_node_id,
                                    edge_type="produces"
                                )
                            except Exception: pass
                    elif tool == "focus":
                        tool_output = self._handle_focus(content)
                    else:
                        tool_output = f"ERROR: Unknown tool '{tool}'."

            except Exception as e:
                tool_output = format_error(e, verbose=self.verbose_mode)
                if self.verbose_mode:
                    traceback.print_exc()
                logger.error(f"Tool execution error: {type(e).__name__}: {e}")

            if tool_output:
                await self._process_tool_output(tool_output, tool, chat_context, safe_send_message)

        return True

    # ── Tool output processing ──────────────────────────────────────

    async def _process_tool_output(
        self,
        tool_output: str,
        tool: str,
        chat_context: Dict[str, Any],
        safe_send_message: callable,
    ) -> None:
        """Handle tool output: log, compact context, send feedback."""
        log_status("📡", "Feedback", f"{len(tool_output)} chars", telemetry=self.telemetry)
        self.telemetry.log_interaction(
            "system", f"Tool Output ({tool.upper()}):\n{tool_output}", "tool_output"
        )
        self.conversation.add_turn("tool", tool_output, tool_output=True)

        if self.conversation.needs_compaction():
            log_status("🗜️", "Auto-compacting context window", telemetry=self.telemetry)
            result = self.conversation.compact()
            if self.verbose_mode:
                print(f"  {Fore.YELLOW}{result}{Style.RESET_ALL}")

        feedback_msg = (
            f"TOOL_OUTPUT ({tool.upper()}):\n{tool_output}\n\n"
            f"[AUTO-PROCEED]: Continuing task execution..."
        )
        response = await safe_send_message(chat_context["chat"], feedback_msg)
        self.conversation.add_turn("assistant", response.text)

        if self.verbose_mode:
            print(
                f"  {Fore.WHITE}[Feedback Response]: {response.text[:200]}...{Style.RESET_ALL}"
            )

        await self.execute(response.text, chat_context, safe_send_message)

    # ── Field parsing ───────────────────────────────────────────────

    @staticmethod
    def _parse_fields(content: str) -> Dict[str, str]:
        """Parse key:value fields from unstructured tool block content."""
        fields: Dict[str, str] = {}
        lines = content.splitlines()
        current_key: Optional[str] = None
        current_value: List[str] = []

        for line in lines:
            found_key = False
            for k in ToolExecutor.KNOWN_KEYS:
                if line.lower().startswith(f"{k}:"):
                    if current_key:
                        fields[current_key] = "\n".join(current_value).strip()
                    current_key = k
                    current_value = [line[len(k) + 1 :].strip()]
                    found_key = True
                    break
            if not found_key and current_key:
                current_value.append(line)

        if current_key:
            fields[current_key] = "\n".join(current_value).strip()
        return fields

    @staticmethod
    def is_safe_path(path: str, workspace_root: Optional[Path] = None) -> bool:
        """Check if a path is within the workspace boundary."""
        try:
            abs_path = Path(path).resolve()
            root = workspace_root or Path.cwd()
            return str(abs_path).startswith(str(root.resolve()))
        except Exception:
            return False

    # ── Handler: delegate ───────────────────────────────────────────

    async def _handle_delegate(
        self,
        tool: str,
        content: str,
        chat_context: Dict[str, Any],
        known_agents: List[str],
        safe_send_message: callable,
    ) -> str:
        fields = self._parse_fields(content)
        agent_name = (
            tool.lower()
            if tool.lower() in known_agents
            else fields.get("agent", "").lower()
        )
        task = fields.get("task", "") if "task" in fields else content.strip()

        if not agent_name or not task:
            return "ERROR: Missing agent or task for delegation."

        log_status("↗️", f"Delegating to {agent_name.upper()}", telemetry=self.telemetry)

        if agent_name not in self.agent_sessions:
            spec_path = self.workspace_root / "agents" / f"{agent_name}.md"
            spec_text = ""
            if spec_path.exists() and spec_path.stat().st_size > 0:
                spec_text = read_file_surgical(spec_path, max_lines=300)
            else:
                fallback_path = self.workspace_root / "agents" / "specialized.md"
                if fallback_path.exists():
                    spec_text = read_file_surgical(fallback_path, max_lines=300)
                else:
                    spec_text = f"You are the {agent_name.upper()} AGENT."

            sub_chat = chat_context["client"].start_chat()

            base_path = self.workspace_root / "GEM_INSTRUCTIONS.md"
            base_instructions = read_file_surgical(base_path, max_lines=400) if base_path.exists() else ""

            try:
                priming = self.prompt_registry.render(
                    "agent_priming",
                    spec_text=spec_text,
                    agents_instructions=chat_context.get('agents_instructions', 'No AGENTS.md instructions loaded.'),
                    agent_registry=chat_context.get('agent_registry', 'No agent registry loaded.'),
                    workspace_context=chat_context.get('workspace_context', 'No workspace context loaded.'),
                    base_instructions=base_instructions,
                )
            except Exception:
                # Fallback to direct construction
                priming = (
                    f"SYSTEM INSTRUCTIONS:\n{spec_text}\n\n"
                    f"PROJECT INSTRUCTIONS (AGENTS.md):\n"
                    f"{chat_context.get('agents_instructions', '')}\n\n"
                    f"AGENT REGISTRY:\n{chat_context.get('agent_registry', '')}\n\n"
                    f"WORKSPACE CONTEXT:\n{chat_context.get('workspace_context', '')}\n\n"
                    f"TOOL PROTOCOLS:\n{base_instructions}\n\n"
                    "INITIALIZATION: Start session. Execute tasks immediately using tool blocks."
                )
            await safe_send_message(sub_chat, priming)
            self.agent_sessions[agent_name] = sub_chat

        sub_chat = self.agent_sessions[agent_name]
        self.telemetry.log_interaction(
            "communicator", f"DELEGATE TO {agent_name}: {task}", "delegation"
        )
        sub_response = await safe_send_message(sub_chat, f"TASK: {task}")

        if not sub_response or not sub_response.text:
            log_status("❌", f"{agent_name.upper()} returned empty response", telemetry=self.telemetry)
            return (
                f"ERROR: Agent {agent_name.upper()} returned an empty response "
                "(likely a safety refusal)."
            )

        self.telemetry.log_interaction(agent_name, sub_response.text, "agent_response")
        await self.execute(sub_response.text, chat_context, safe_send_message)
        log_status("↙️", f"{agent_name.upper()} complete", telemetry=self.telemetry)

        return (
            f"AGENT {agent_name.upper()} completed task.\n"
            f"Response: {sub_response.text}"
        )

    # ── Handler: focus ──────────────────────────────────────────────

    def _handle_focus(self, content: str) -> str:
        fields = self._parse_fields(content)
        path = fields.get("path", ".").strip()
        depth = int(fields.get("depth", "2"))
        if not self.is_safe_path(path, self.workspace_root):
            return "ERROR: Path outside workspace boundary."
        return get_directory_context(Path(path), depth=depth)

    # ── Handler: field parsing ──────────────────────────────────────


# ── Simple progress spinner ──────────────────────────────────

class Spinner:
    """Minimal async spinner for terminal progress indication."""
    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, message: str = ""):
        self.message = message
        self._running = False
        self._task = None
    
    async def _spin(self):
        """Animate the spinner until stopped."""
        while self._running:
            for frame in self._FRAMES:
                if not self._running:
                    break
                import sys
                sys.stdout.write(f"\r{frame} {self.message}")
                sys.stdout.flush()
                await asyncio.sleep(0.08)
        # Clear the spinner line
        import sys
        sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
        sys.stdout.flush()
    
    async def __aenter__(self):
        self._running = True
        self._task = asyncio.create_task(self._spin())
        return self
    
    async def __aexit__(self, *args):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

