import asyncio
import sys
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from gemini_webapi import GeminiClient
from smart_context import get_workspace_context

# Load environment variables from .env file
load_dotenv()

SECURE_1PSID = os.getenv("SECURE_1PSID")
SECURE_1PSIDTS = os.getenv("SECURE_1PSIDTS")

class ToolExecutor:
    @staticmethod
    async def execute(response_text, chat_context):
        # Regex to find tool blocks
        blocks = re.findall(r"```tool:(\w+)\n(.*?)\n```", response_text, re.DOTALL)
        if not blocks:
            return False

        for tool, content in blocks:
            print(f"\n[🛠️ EXECUTING: {tool}]")
            try:
                if tool == "delegate":
                    # Multi-agent orchestration
                    lines = content.splitlines()
                    agent_name = [l for l in lines if l.startswith("agent:")][0].replace("agent:", "").strip().lower()
                    task = content.split("task:")[1].strip()
                    
                    print(f"Delegating to {agent_name}...")
                    
                    # Determine which instruction file to load
                    if agent_name == "overseer":
                        spec_path = Path("/data/data/com.termux/files/home/dev/ww/agents/overseer.md")
                    elif agent_name == "communicator":
                        spec_path = Path("/data/data/com.termux/files/home/dev/ww/agents/communicator.md")
                    else:
                        spec_path = Path("/data/data/com.termux/files/home/dev/ww/agents/specialized.md")
                    
                    spec_text = spec_path.read_text() if spec_path.exists() else f"You are the {agent_name.upper()} AGENT."
                    
                    # Create a new sub-session for the delegate
                    sub_chat = chat_context['client'].start_chat()
                    
                    # Include tool protocols in the priming of every sub-agent
                    base_instr_path = Path("/data/data/com.termux/files/home/dev/ww/GEM_INSTRUCTIONS.md")
                    base_instructions = base_instr_path.read_text() if base_instr_path.exists() else ""
                    
                    priming = (
                        f"SYSTEM INSTRUCTIONS:\n{spec_text}\n\n"
                        f"TOOL PROTOCOLS:\n{base_instructions}\n\n"
                        f"TASK: {task}"
                    )
                    
                    sub_response = await sub_chat.send_message(priming)
                    
                    # Recursive tool execution for sub-agents
                    sub_context = {'client': chat_context['client'], 'chat': sub_chat}
                    await ToolExecutor.execute(sub_response.text, sub_context)
                    
                    print(f"\n[{agent_name.upper()} FINAL RESPONSE]: {sub_response.text}\n")
                    
                    # Feed sub-agent result back to caller
                    await chat_context['chat'].send_message(f"SYSTEM: {agent_name} has completed the task. Result: {sub_response.text}")
                
                elif tool == "read":
                    path = content.strip()
                    print(f"Reading: {path}")
                    print("-" * 20)
                    print(Path(path).read_text())
                    print("-" * 20)
                
                elif tool == "write":
                    lines = content.splitlines()
                    path_line = [l for l in lines if l.startswith("filepath:")][0]
                    filepath = path_line.replace("filepath:", "").strip()
                    content_start = content.find("content:") + len("content:")
                    file_content = content[content_start:].strip()
                    Path(filepath).write_text(file_content)
                    print(f"✅ Wrote to {filepath}")

                elif tool == "shell":
                    cmd = content.strip()
                    print(f"Running: {cmd}")
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if stdout: print(stdout.decode())
                    if stderr: print(f"Error: {stderr.decode()}")
                
                elif tool == "list":
                    path = content.strip() or "."
                    print(f"Listing directory: {path}")
                    files = os.listdir(path)
                    print("-" * 20)
                    for f in sorted(files):
                        p = os.path.join(path, f)
                        suffix = "/" if os.path.isdir(p) else ""
                        print(f"{f}{suffix}")
                    print("-" * 20)

                elif tool == "search":
                    pattern = ""
                    search_path = "."
                    for line in content.splitlines():
                        if line.startswith("pattern:"):
                            pattern = line.replace("pattern:", "").strip()
                        elif line.startswith("path:"):
                            search_path = line.replace("path:", "").strip()
                    
                    print(f"Searching for '{pattern}' in {search_path}...")
                    cmd = f"find {search_path} -maxdepth 3 -name '*{pattern}*' && grep -rli '{pattern}' {search_path} | head -n 20"
                    process = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    print("-" * 20)
                    if stdout: print(stdout.decode())
                    if stderr: print(f"Error: {stderr.decode()}")
                    print("-" * 20)
                
                elif tool == "replace":
                    lines = content.splitlines()
                    filepath = [l for l in lines if l.startswith("filepath:")][0].replace("filepath:", "").strip()
                    find_start = content.find("find:") + len("find:")
                    replace_start = content.find("replace:") + len("replace:")
                    old_str = content[find_start:replace_start - len("replace:")].strip()
                    new_str = content[replace_start:].strip()
                    
                    file_path = Path(filepath)
                    text = file_path.read_text()
                    if old_str in text:
                        file_path.write_text(text.replace(old_str, new_str))
                        print(f"✅ Replaced text in {filepath}")
                    else:
                        print(f"❌ Could not find target text in {filepath}")

            except Exception as e:
                print(f"❌ Tool Error: {e}")
        return True

async def main():
    if not SECURE_1PSID or not SECURE_1PSIDTS:
        print("Error: SECURE_1PSID and SECURE_1PSIDTS must be set in .env file")
        return

    # Establish connection layer
    client = GeminiClient(SECURE_1PSID, SECURE_1PSIDTS)
    await client.init(timeout=30, auto_refresh=True)
    
    # Initialize state tracking chat object
    chat = client.start_chat()
    chat_context = {'client': client, 'chat': chat}

    # Load Communicator Instructions
    comm_path = Path("/data/data/com.termux/files/home/dev/ww/agents/communicator.md")
    comm_instructions = comm_path.read_text() if comm_path.exists() else ""
    
    # Load Base Tool Instructions
    base_instr_path = Path("/data/data/com.termux/files/home/dev/ww/GEM_INSTRUCTIONS.md")
    base_instructions = base_instr_path.read_text() if base_instr_path.exists() else ""

    # Pre-calculate workspace context
    print("[*] Gathering workspace context...")
    workspace_context = get_workspace_context()

    # Combine Instructions and Context
    priming_message = (
        f"YOUR IDENTITY:\n{comm_instructions}\n\n"
        f"BASE TOOL PROTOCOLS:\n{base_instructions}\n\n"
        f"INITIAL WORKSPACE CONTEXT:\n{workspace_context}\n\n"
        "Acknowledge your role as COMMUNICATOR. Use 'tool:delegate' to invoke the OVERSEER for technical tasks."
    )

    if len(sys.argv) > 1:
        user_prompt = sys.argv[1]
        print("[*] Priming session and dispatching request...")
        full_payload = f"{priming_message}\n\nUSER REQUEST: {user_prompt}"
        response = await chat.send_message(full_payload)
        print("\n=== SYSTEM OUT ===")
        print(response.text)
        await ToolExecutor.execute(response.text, chat_context)
        print("==================\n")
    else:
        print("--- Gemini 3-Tier Multi-Agent System ---")
        print("Type 'exit' or 'quit' to end the session.\n")
        
        print("[*] Priming session as COMMUNICATOR...")
        await chat.send_message(priming_message)
        print("[+] Hierarchy Active: User <-> Communicator <-> Overseer <-> Specialists.")

        while True:
            try:
                user_prompt = input("\nYou: ").strip()
                if not user_prompt: continue
                if user_prompt.lower() in ("exit", "quit"): break

                print("[*] Waiting for response...")
                response = await chat.send_message(user_prompt)
                print(f"\nResponse: {response.text}")
                
                await ToolExecutor.execute(response.text, chat_context)

            except KeyboardInterrupt: break
            except Exception as e: print(f"\n[!] Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
