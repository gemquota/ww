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
    async def execute(response_text):
        # Regex to find tool blocks
        blocks = re.findall(r"```tool:(\w+)\n(.*?)\n```", response_text, re.DOTALL)
        if not blocks:
            return False

        for tool, content in blocks:
            print(f"\n[🛠️ EXECUTING: {tool}]")
            try:
                if tool == "read":
                    path = content.strip()
                    print(f"Reading: {path}")
                    print("-" * 20)
                    print(Path(path).read_text())
                    print("-" * 20)
                
                elif tool == "write":
                    # Simple parser for write blocks
                    lines = content.splitlines()
                    path_line = [l for l in lines if l.startswith("filepath:")][0]
                    filepath = path_line.replace("filepath:", "").strip()
                    # Find where content starts
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
                    # Using find for filenames and grep for content
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

    # Load System Instructions for the "Gem" behavior
    instructions_path = Path("/data/data/com.termux/files/home/dev/ww/GEM_INSTRUCTIONS.md")
    system_instructions = instructions_path.read_text() if instructions_path.exists() else ""

    # Pre-calculate workspace context
    print("[*] Gathering workspace context...")
    workspace_context = get_workspace_context()

    # Combine Instructions and Context for the "Priming" message
    priming_message = (
        f"SYSTEM INSTRUCTIONS:\n{system_instructions}\n\n"
        f"INITIAL WORKSPACE CONTEXT:\n{workspace_context}\n\n"
        "Please acknowledge these instructions and the workspace context. "
        "From now on, respond as the Codebase Engineer Gem using the tool protocols defined."
    )

    if len(sys.argv) > 1:
        # One-shot mode
        user_prompt = sys.argv[1]
        print("[*] Priming session and dispatching request...")
        # In one-shot, we must send everything because there's no persistent state after this script ends
        full_payload = f"{priming_message}\n\nUSER REQUEST: {user_prompt}"
        response = await chat.send_message(full_payload)
        print("\n=== SYSTEM OUT ===")
        print(response.text)
        await ToolExecutor.execute(response.text)
        print("==================\n")
    else:
        # Interactive mode
        print("--- Gemini Agentic Bridge (Stateful) ---")
        print("Type 'exit' or 'quit' to end the session.\n")
        
        print("[*] Priming session with Instructions and Workspace Context...")
        # This priming happens ONCE per session
        await chat.send_message(priming_message)
        print("[+] Session primed. Gemini is now project-aware.")

        while True:
            try:
                user_prompt = input("\nYou: ").strip()
                if not user_prompt:
                    continue
                if user_prompt.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break

                print("[*] Waiting for response...")
                # Subsequent messages ONLY send the user prompt; Gemini remembers the rest
                response = await chat.send_message(user_prompt)
                print(f"\nGemini: {response.text}")
                
                # Check for and execute tools
                await ToolExecutor.execute(response.text)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\n[!] Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
