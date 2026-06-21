import asyncio
import os
import sys
import argparse
import shutil
import textwrap
import json
import time
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from colorama import Fore, Style, init as colorama_init
import threading

colorama_init(autoreset=True)

from core.agent import GemmaOutlinesAgent
from core.memory import MemoryManager
from core.router import IntentRouter
from core.benchmarker import BenchmarkHarness, BenchmarkJudge, ExecutionTrace, TraceStep
from core.schemas import ToolCall
from tools.registry import ToolRegistry
from tools.system_tools import (
    read_file, list_dir, write_file, shell_exec, git_tool, doc_search, request_clarification,
    ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs, UpdateScratchpadArgs, GitArgs, DocSearchArgs, ClarificationArgs
)
from utils.agents_loader import load_instructions, load_agent_specs
from utils.repo_mapper import RepoMapper
from dotenv import load_dotenv
from gfx.mascot_tui import Mascot

load_dotenv()

# Optional: Import for Auto-Heal escalation
try:
    from utils.web_client import WebGeminiClient
    HAS_WEB_API = True
except ImportError:
    HAS_WEB_API = False

from core.healing import AutoHealer
from core.judge import BenchmarkJudge

from core.telemetry import telemetry

class GemmaHarness:
    def __init__(self, model_path: str, yolo: bool = False, session_name: str = "default", auto_heal: bool = True, web_memory: bool = False, use_mascot: bool = True):
        print(f"DEBUG: GemmaHarness initialized with use_mascot={use_mascot}")
        self.agent = GemmaOutlinesAgent(model_path)
        self.memory = MemoryManager(session_name=session_name, use_web_memory=web_memory)
        self.session_id = self.memory.session_id
        self.agent.session_id = self.session_id
        self.registry = ToolRegistry()
        self.router = IntentRouter(self.agent)
        self.repo_mapper = RepoMapper(Path(os.getcwd()))
        self.yolo = yolo
        self.auto_heal = auto_heal
        self.healer = AutoHealer() if auto_heal and HAS_WEB_API else None
        self.workspace_root = Path(os.getcwd())
        self._setup_tools()
        
        # Mascot Integration
        self.use_mascot = use_mascot
        self.mascot = Mascot() if use_mascot else None
        if self.mascot:
            self.mascot_thread = threading.Thread(target=self.mascot.update, daemon=True)
            self.mascot_thread.start()

        telemetry.log(self.session_id, "session_start", {
            "model_path": model_path,
            "yolo": yolo,
            "auto_heal": auto_heal,
            "web_memory": web_memory
        })

    def _safe_print(self, text: str, color: str = ""):
        """Prints text wrapped to 84% of the terminal width to avoid mascot overlap."""
        cols, _ = shutil.get_terminal_size()
        wrap_width = max(20, int(cols * 0.84))
        # Handle existing newlines by splitting and wrapping each part
        lines = text.split('\n')
        for line in lines:
            wrapped = textwrap.fill(line, width=wrap_width, replace_whitespace=False)
            print(f"{color}{wrapped}{Style.RESET_ALL}")

    def _setup_tools(self):
        self.registry.register("read_file", read_file, "Read contents of a file.", ReadFileArgs)
        self.registry.register("write_file", write_file, "Write contents to a file.", WriteFileArgs)
        self.registry.register("list_dir", list_dir, "List files in a directory.", ListDirArgs)
        self.registry.register("shell_exec", shell_exec, "Execute a shell command.", ShellExecArgs)
        self.registry.register("git", git_tool, "Execute git commands.", GitArgs)
        self.registry.register("update_scratchpad", self.memory.update_scratchpad, "Update external state.", UpdateScratchpadArgs)
        self.registry.register("doc_search", doc_search, "Search project documentation.", DocSearchArgs)
        self.registry.register("request_clarification", request_clarification, "Ask the user for more information.", ClarificationArgs)

    def shutdown(self):
        """Properly shuts down the harness and its components."""
        if self.mascot:
            self.mascot.shutdown()
        telemetry.export_to_markdown(self.session_id)

    async def run_loop(self, user_input: str, fix_strategy: Optional[str] = None):
        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        telemetry.log(self.session_id, "turn_start", {"user_input": user_input, "fix_strategy": fix_strategy})
        
        # Add to memory only once
        self.memory.add_turn("user", user_input)

        retry_count = 0
        max_retries = 2 # 2 retries locally (3 total attempts)
        
        task_query = user_input
        if fix_strategy:
            task_query = f"RESUMING TASK WITH FIX STRATEGY:\n{fix_strategy}\n\nORIGINAL TASK: {user_input}"

        while retry_count <= max_retries:
            print(f"\n[Attempt {retry_count + 1}/{max_retries + 1}]")
            
            # Step 1: Detect Intent
            self._safe_print("Identifying intent...", color=Fore.BLUE + "[Router]: ")
            intent = self.router.route(task_query)
            self._safe_print(f"Detected Intent: {Fore.CYAN}{intent}", color=Fore.BLUE + "[Router]: ")
            
            # telemetry.log is now handled inside router.route()

            success = await self._execute_task(task_query, intent=intent)
            
            if success:
                break
            
            retry_count += 1
            if retry_count <= max_retries:
                self._safe_print(f"Task failed. Summarizing failure and retrying (Attempt {retry_count + 1})...", color=Fore.YELLOW + "[Error Recovery]: ")
                telemetry.log(self.session_id, "error_recovery", {"attempt": retry_count, "status": "retrying"})
            else:
                report = (
                    "🚨 ESCALATION_REPORT 🚨\n"
                    f"SESSION: {self.memory.session_id}\n"
                    f"ORIGINAL_TASK: {user_input}\n"
                    f"STATUS: Failed after {max_retries + 1} attempts.\n"
                    "LAST_OBSERVATIONS: See session history."
                )
                print("\n" + "="*40 + "\n" + report + "\n" + "="*40)
                telemetry.log(self.session_id, "escalation", {"report": report})

                if self.auto_heal and HAS_WEB_API:
                    self._safe_print("Attempting autonomous escalation to Gemini Bridge...", color=Fore.MAGENTA + "[Auto-Heal]: ")
                    fix = await self._get_cloud_diagnosis(report)
                    if fix:
                        self._safe_print("Received fix strategy. Restarting loop...", color=Fore.MAGENTA + "[Auto-Heal]: ")
                        # Recursively call run_loop with the new fix
                        await self.run_loop(user_input, fix_strategy=fix)
                        return
                
                self._safe_print("Local agent failed. Escalating to Gemini Bridge for Diagnosis & Fix.", color=Fore.RED + "[Escalation]: ")
                print("\n[Pause]: Waiting for external fix (use --fix 'strategy').")
        
        telemetry.export_to_markdown(self.session_id)

    async def _get_cloud_diagnosis(self, report: str) -> Optional[str]:
        """Sends the failure report to Gemini for a fix strategy."""
        if not HAS_WEB_API:
            return None
        
        try:
            client = WebGeminiClient()
            if not await client.init():
                self._safe_print("Skipping cloud diagnosis (Could not initialize WebGeminiClient).", color=Fore.YELLOW + "[Auto-Heal]: ")
                return None

            prompt = (
                f"You are the GEMINI BRIDGE for a local Gemma 2B agent.\n"
                f"The local agent has failed a task. Review the report and provide a DENSED FIX STRATEGY.\n"
                f"Your strategy will be injected back into the 2B agent's loop.\n\n"
                f"{report}\n\n"
                f"Focus on the root cause and a step-by-step correction. Keep it under 200 words."
            )
            return await client.ask(prompt)
        except Exception as e:
            self._safe_print(f"{e}", color=Fore.RED + "[Auto-Heal Error]: ")
            return None

    async def _handle_command(self, cmd: str):
        parts = cmd.lower().split()
        c = parts[0]
        if c == "/clear":
            self.agent.clear_history()
            self.memory.clear_history() # Ensure memory is also cleared
            print(f"{Fore.YELLOW}Conversation history and memory cleared.{Style.RESET_ALL}")
        elif c == "/history":
            history = self.memory.get_history()
            if not history:
                print(f"{Fore.YELLOW}No history found.{Style.RESET_ALL}")
                return
            print(f"\n{Fore.BLUE}--- Session History ---{Style.RESET_ALL}")
            for h in history:
                color = Fore.CYAN if h.role == 'user' else Fore.GREEN
                print(f"{color}{h.role.upper()}:{Style.RESET_ALL} {h.content}")
        elif c == "/help":
            print(f"\n{Fore.BLUE}--- Available Commands ---{Style.RESET_ALL}")
            print(f"{Fore.CYAN}/clear{Style.RESET_ALL}   - Clear conversation history and memory.")
            print(f"{Fore.CYAN}/history{Style.RESET_ALL} - Show the full session history.")
            print(f"{Fore.CYAN}/help{Style.RESET_ALL}    - Show this help message.")
            print(f"{Fore.CYAN}exit/quit{Style.RESET_ALL}- Exit the interactive mode.")
        else:
            print(f"{Fore.RED}Unknown command: {c}. Type /help for available commands.{Style.RESET_ALL}")

    async def execute_task_with_trace(self, user_input: str, trace: ExecutionTrace, intent: str = "GENERAL") -> bool:
        """Executes a task while recording every step in the trace."""
        self.memory.add_turn("user", user_input)
        
        instructions = load_instructions(self.workspace_root)
        agent_specs = load_agent_specs(self.workspace_root)
        repo_map = self.repo_mapper.generate_map()
        
        allowed_tools = self.router.get_tools_for_intent(intent, list(self.registry.tools.keys()))
        tool_defs = "AVAILABLE TOOLS:\n"
        for t_name in allowed_tools:
            tool_defs += self.registry.get_tool_summary(t_name, full=False) + "\n"

        system_prompt = (
            "You are a helpful AI assistant that uses tools via JSON.\n\n"
            "### MANDATORY OUTPUT FORMAT\n"
            "You must ALWAYS respond with a SINGLE JSON object. No other text, no markdown blocks.\n"
            "Schema:\n"
            "{\n"
            '  "thought": "Plan your NEXT step here. Be specific.",\n'
            '  "tool_name": "tool_to_use" or null,\n'
            '  "tool_args": {"arg1": "val1"} or null,\n'
            '  "final_answer": "Final response ONLY if the ENTIRE task is complete" or null\n'
            "}\n\n"
            "### IMPORTANT RULES\n"
            "1. If you need information from a file, you MUST use 'read_file'. Do NOT guess.\n"
            "2. Do NOT provide a 'final_answer' until you have actually verified the result with a tool.\n"
            "3. If both 'tool_name' and 'final_answer' are present, the tool will be executed and 'final_answer' ignored.\n"
            "4. Your 'thought' must explain what you are about to do and why.\n\n"
            "### EXAMPLE TURN\n"
            "User: Read the file 'README.md'\n"
            "Model:\n"
            "{\n"
            '  "thought": "I need to read README.md to understand the project instructions.",\n'
            '  "tool_name": "read_file",\n'
            '  "tool_args": {"file_path": "README.md"},\n'
            '  "final_answer": null\n'
            "}\n\n"
            "### CONTEXT\n"
            f"{instructions}\n"
            f"{self.memory.get_scratchpad_summary()}\n\n"
            "### TOOLS\n"
            f"{tool_defs}\n"
        )
        self.agent.set_system_instructions(system_prompt)

        for i in range(10):
            self.agent.history = await self.memory.process_history(self.agent)
            step = TraceStep(step_number=i+1, thought="")
            try:
                if self.mascot: self.mascot.on_event('THINKING')
                response_obj = self.agent.generate_json("", ToolCall, save_history=False)
                if self.mascot: self.mascot.on_event('IDLE')
                if not isinstance(response_obj, ToolCall):
                    if self.mascot: self.mascot.on_event('ERROR')
                    step.error = "Invalid ToolCall JSON"
                    trace.steps.append(step)
                    return False
            except Exception as e:
                if self.mascot: self.mascot.on_event('ERROR')
                step.error = str(e)
                trace.steps.append(step)
                return False
                
            step.thought = response_obj.thought
            
            # Save response to memory
            self.memory.add_turn("assistant", response_obj.model_dump_json())

            if response_obj.tool_name:
                tool_name = response_obj.tool_name
                tool_args = response_obj.tool_args
                step.tool_name = tool_name
                step.tool_args = tool_args
                
                # Two-Stage Reasoning: If args are missing, inject schema and retry
                if tool_args is None:
                    schema_hint = self.registry.get_tool_summary(tool_name, full=True)
                    self._safe_print(f"Tool selected: {Fore.CYAN}{tool_name}{Style.RESET_ALL}. Injecting schema hint...", color=Fore.BLUE + "[Schema Hint]: ")
                    telemetry.log(self.session_id, "tool_hint", {"tool_name": tool_name})
                    self.memory.add_turn("system", f"TOOL SELECTED: {tool_name}\n{schema_hint}\n\nPlease provide the arguments for this tool in the next turn.")
                    trace.steps.append(step)
                    continue

                telemetry.log(self.session_id, "tool_call", {"tool_name": tool_name, "tool_args": tool_args})
                observation = await self.registry.execute(tool_name, tool_args)
                telemetry.log(self.session_id, "tool_observation", {"observation": observation})
                
                if isinstance(observation, str) and observation.startswith("CLARIFICATION_REQUIRED:"):
                    question = observation.replace("CLARIFICATION_REQUIRED:", "").strip()
                    self._safe_print(f"Agent is asking for clarification: {Fore.YELLOW}{question}", color=Fore.CYAN + "[Collaborative Loop]: ")
                    user_resp = input("Your response: ")
                    observation = f"USER CLARIFICATION: {user_resp}"

                masked_obs = self.memory.mask_observation(observation)
                step.observation = str(masked_obs)
                self.memory.add_turn("system", f"OBSERVATION from {tool_name}:\n{masked_obs}")
                
                trace.steps.append(step)
            elif response_obj.final_answer:
                self.mascot.on_event('SUCCESS')
                trace.final_answer = response_obj.final_answer
                # Final answer is already in memory from assistant turn
                trace.steps.append(step)
                return True
            else:
                trace.steps.append(step)
                return False
        
        return False

    async def _execute_task(self, user_input: str, intent: str = "GENERAL") -> bool:
        self._safe_print(user_input, color=Fore.BLUE + "[User]: ")
        
        # Tiered Context: Rules + Repo Map + Local
        instructions = load_instructions(self.workspace_root)
        agent_specs = load_agent_specs(self.workspace_root)
        repo_map = self.repo_mapper.generate_map()
        
        # Filter tools by intent
        allowed_tools = self.router.get_tools_for_intent(intent, list(self.registry.tools.keys()))
        tool_defs = "AVAILABLE TOOLS (Sub-setted for Intent: " + intent + "):\n"
        for t_name in allowed_tools:
            tool_defs += self.registry.get_tool_summary(t_name, full=False) + "\n"

        system_prompt = (
            "You are a helpful AI assistant that uses tools via JSON.\n\n"
            "### MANDATORY OUTPUT FORMAT\n"
            "You must ALWAYS respond with a SINGLE JSON object. No other text, no markdown blocks.\n"
            "Schema:\n"
            "{\n"
            '  "thought": "Plan your NEXT step here. Be specific.",\n'
            '  "tool_name": "tool_to_use" or null,\n'
            '  "tool_args": {"arg1": "val1"} or null,\n'
            '  "final_answer": "Final response ONLY if the ENTIRE task is complete" or null\n'
            "}\n\n"
            "### IMPORTANT RULES\n"
            "1. If you need information from a file, you MUST use 'read_file'. Do NOT guess.\n"
            "2. Do NOT provide a 'final_answer' until you have actually verified the result with a tool.\n"
            "3. If both 'tool_name' and 'final_answer' are present, the tool will be executed and 'final_answer' ignored.\n"
            "4. Your 'thought' must explain what you are about to do and why.\n\n"
            "### EXAMPLE TURN\n"
            "User: Read the file 'README.md'\n"
            "Model:\n"
            "{\n"
            '  "thought": "I need to read README.md to understand the project instructions.",\n'
            '  "tool_name": "read_file",\n'
            '  "tool_args": {"file_path": "README.md"},\n'
            '  "final_answer": null\n'
            "}\n\n"
            "### CONTEXT\n"
            f"{instructions}\n"
            f"{self.memory.get_scratchpad_summary()}\n\n"
            f"### TOOLS\n"
            f"{tool_defs}\n"
        )
        self.agent.set_system_instructions(system_prompt)
        telemetry.log(self.session_id, "priming", {"instructions": system_prompt})

        for i in range(10):  # Max 10 iterations
            self.agent.history = await self.memory.process_history(self.agent)
            try:
                if self.mascot: self.mascot.on_event('THINKING')
                # Message is empty because user_input is already in history
                response_obj = self.agent.generate_json("", ToolCall, save_history=False)
                if self.mascot: self.mascot.on_event('IDLE')
                
                if not isinstance(response_obj, ToolCall):
                    if self.mascot: self.mascot.on_event('ERROR')
                    self._safe_print("Model failed to produce valid ToolCall JSON.", color=Fore.RED + "[Format Error]: ")
                    return False
            except Exception as e:
                if self.mascot: self.mascot.on_event('ERROR')
                self._safe_print(f"{e}", color=Fore.RED + "[Critical Generation Error]: ")
                return False
                
            self._safe_print(response_obj.thought, color=Fore.MAGENTA + "[Thought]: ")
            
            # Save response to memory
            self.memory.add_turn("assistant", response_obj.model_dump_json())

            # Change Priority: Tool Call first
            if response_obj.tool_name:
                tool_name = response_obj.tool_name
                tool_args = response_obj.tool_args
                
                # Two-Stage Reasoning: If args are missing, inject schema and retry
                if tool_args is None:
                    schema_hint = self.registry.get_tool_summary(tool_name, full=True)
                    self._safe_print(f"Tool selected: {Fore.CYAN}{tool_name}{Style.RESET_ALL}. Injecting schema hint...", color=Fore.BLUE + "[Schema Hint]: ")
                    telemetry.log(self.session_id, "tool_hint", {"tool_name": tool_name})
                    self.memory.add_turn("system", f"TOOL SELECTED: {tool_name}\n{schema_hint}\n\nPlease provide the arguments for this tool in the next turn.")
                    continue

                self._safe_print(f"{tool_name}({tool_args})", color=Fore.YELLOW + "[Tool Call]: ")
                telemetry.log(self.session_id, "tool_call", {"tool_name": tool_name, "tool_args": tool_args})
                
                if not self.yolo:
                    confirm = input(f"  Confirm execution of {tool_name}? (y/n/yolo): ").lower()
                    if confirm == 'yolo':
                        self.yolo = True
                    elif confirm != 'y':
                        self._safe_print("Aborted by user", color=Fore.RED + "[Aborted]: ")
                        telemetry.log(self.session_id, "tool_aborted", {"tool_name": tool_name})
                        return False
                
                observation = await self.registry.execute(tool_name, tool_args)
                
                if isinstance(observation, str) and observation.startswith("CLARIFICATION_REQUIRED:"):
                    question = observation.replace("CLARIFICATION_REQUIRED:", "").strip()
                    self._safe_print(f"Agent is asking for clarification: {Fore.YELLOW}{question}", color=Fore.CYAN + "[Collaborative Loop]: ")
                    user_resp = input("Your response: ")
                    observation = f"USER CLARIFICATION: {user_resp}"
                    telemetry.log(self.session_id, "clarification", {"question": question, "answer": user_resp})

                masked_obs = self.memory.mask_observation(observation)
                self._safe_print(f"{masked_obs}", color=Fore.CYAN + "[Observation]: ")
                telemetry.log(self.session_id, "tool_observation", {"tool_name": tool_name, "observation": str(masked_obs)})
                
                self.memory.add_turn("system", f"OBSERVATION from {tool_name}:\n{masked_obs}")
            elif response_obj.final_answer:
                if self.mascot: self.mascot.on_event('SUCCESS')
                self._safe_print(response_obj.final_answer, color=Fore.GREEN + "[Agent]: ")
                # assistant turn already added above
                return True
            else:
                if self.mascot: self.mascot.on_event('IDLE')
                return False
        
        if self.mascot: self.mascot.on_event('IDLE')
        return False

async def main():
    parser = argparse.ArgumentParser(
        description="Gemma 2B Agent Harness: A standalone, local-first agent with autonomous tool use.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  2b                                      # Start interactive session (Auto-Heal ON)
  2b -m                                   # Start interactive session (Auto-Heal OFF)
  2b -y "Create a new git branch 'feat/x'" # Run a single task in YOLO mode
  2b -s debug_session                     # Start/Resume a specific named session
        """
    )
    
    parser.add_argument("-y", "--yolo", action="store_true", 
                        help="Enable YOLO mode (bypass tool execution confirmations)")
    
    parser.add_argument("-m", "--manual", action="store_true", 
                        help="Disable autonomous mode (prevent automatic escalation to Gemini Bridge)")
    
    parser.add_argument("-s", "--session", default="default", metavar="NAME",
                        help="Session name for SQLite persistence (default: 'default')")
    
    parser.add_argument("-w", "--web-memory", action="store_true",
                        help="Use Gemini Web for memory compression/summarization (high quality)")
    
    parser.add_argument("-M", "--model", metavar="PATH",
                        default="/data/data/com.termux/files/home/local_ai/llama.cpp/gemma-2b.gguf", 
                        help="Path to the Gemma 2B GGUF model file")
    
    parser.add_argument("-f", "--fix", metavar="STRATEGY",
                        help="Inject a specific fix strategy (usually provided by an external orchestrator)")

    parser.add_argument("-B", "--benchmark", action="store_true",
                        help="Run the benchmarking suite")
    
    parser.add_argument("--no-mascot", action="store_true",
                        help="Disable mascot animations")
    
    parser.add_argument("--run-all", action="store_true", help="Run all available benchmark suites")
    parser.add_argument("--suite", help="Path to a specific benchmark suite JSON file")
    
    parser.add_argument("query", nargs="?", 
                        help="Optional single task query. If omitted, starts interactive mode.")
    
    args = parser.parse_args()
    
    # Auto-Heal is ON by default, disabled ONLY by -m/--manual
    auto_heal = not args.manual
    # Mascot is ON by default, disabled by --no-mascot or in benchmark mode
    use_mascot = not args.no_mascot and not args.benchmark
    
    if not os.path.exists(args.model):
        print(f"{Fore.RED}Error: Model not found at {args.model}{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}       GEMMA 2B AGENT HARNESS - STANDALONE CLI")
    if args.benchmark:
        print(f"{Fore.CYAN}       Mode: {Fore.YELLOW}BENCHMARKING{Fore.CYAN}")
    else:
        print(f"{Fore.CYAN}       Session: {Fore.YELLOW}{args.session}{Fore.CYAN} | Mode: {Fore.YELLOW}{'YOLO' if args.yolo else 'SAFE'}{Fore.CYAN}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    if args.benchmark:
        os.environ["BENCHMARK_MODE"] = "1"

    harness = GemmaHarness(args.model, yolo=args.yolo, session_name=args.session, auto_heal=auto_heal, web_memory=args.web_memory, use_mascot=use_mascot)
    
    if args.benchmark:
        suites = []
        if args.run_all:
            suites = list(Path("benchmarks").glob("*.json"))
        elif args.suite:
            suites = [Path(args.suite)]
        
        if not suites:
            print(f"{Fore.RED}No benchmark suites found.{Style.RESET_ALL}")
            return
            
        # Initialize Judge if Web API is available
        judge = None
        if HAS_WEB_API:
            try:
                client = WebGeminiClient()
                if await client.init():
                    judge = BenchmarkJudge(client)
                    print(f"{Fore.GREEN}Judge Agent (Gemini Web) initialized.{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}Warning: Could not initialize WebGeminiClient for Judge.{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not initialize Judge Agent: {e}{Style.RESET_ALL}")

        bench_harness = BenchmarkHarness(harness, judge=judge)
        
        all_results = []
        for suite in suites:
            print(f"\n{Fore.BLUE}--- Running Suite: {suite.name} ---{Style.RESET_ALL}")
            suite_results = await bench_harness.run_suite(str(suite))
            all_results.extend(suite_results)
            
        # Summary Report
        print(f"\n{Fore.CYAN}{'='*40}")
        print(f"{Fore.CYAN}       BENCHMARK SUMMARY")
        print(f"{Fore.CYAN}{'='*40}")
        passed = sum(1 for r in all_results if r.success)
        total = len(all_results)
        avg_precision = sum(r.precision for r in all_results if r.precision is not None) / total if total > 0 else 0
        avg_recall = sum(r.recall for r in all_results if r.recall is not None) / total if total > 0 else 0
        avg_info_loss = sum(r.info_loss for r in all_results if r.info_loss is not None) / total if total > 0 else 0

        print(f"Total Tasks: {total}")
        print(f"Passed:      {Fore.GREEN if passed == total else Fore.YELLOW}{passed}{Style.RESET_ALL}")
        print(f"Failed:      {Fore.RED if passed < total else Fore.GREEN}{total - passed}{Style.RESET_ALL}")
        if total > 0:
            print(f"Success Rate: {(passed/total)*100:.1f}%")
            print(f"Avg Precision: {avg_precision:.2f}")
            print(f"Avg Recall:    {avg_recall:.2f}")
            print(f"Avg Info Loss: {avg_info_loss:.2f}")
        
        # Write failure analysis
        failures = [r for r in all_results if not r.success]
        if failures:
            analysis = [
                {
                    "task_id": f.task_id,
                    "reason": f.reason,
                    "trace_path": f.trace_path
                }
                for f in failures
            ]
            analysis_path = Path("benchmarks/failure_analysis.json")
            with open(analysis_path, "w") as f:
                json.dump(analysis, f, indent=2)
            print(f"\nFailure analysis written to: {Fore.YELLOW}{analysis_path}{Style.RESET_ALL}")
            
        return

    if args.query:
        await harness.run_loop(args.query, fix_strategy=args.fix)
        return
    
    print("\n--- 2B AGENT INTERACTIVE MODE ---")
    print("Agent Active. Type 'exit' to quit.")
    while True:
        try:
            user_input = input("\n> ")
            if user_input.lower() in ('exit', 'quit'):
                if harness.mascot: harness.mascot.shutdown()
                break
            await harness.run_loop(user_input, fix_strategy=args.fix)
        except KeyboardInterrupt:
            if harness.mascot: harness.mascot.shutdown()
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
