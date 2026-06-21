import os
import subprocess
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

# Tool Schemas
class ReadFileArgs(BaseModel):
    file_path: str = Field(..., description="Path to the file to read.")

class ListDirArgs(BaseModel):
    dir_path: str = Field(".", description="Path to the directory to list.")

class WriteFileArgs(BaseModel):
    file_path: str = Field(..., description="Path to the file to write.")
    content: str = Field(..., description="The content to write to the file.")

class ShellExecArgs(BaseModel):
    command: str = Field(..., description="The shell command to execute.")

class UpdateScratchpadArgs(BaseModel):
    key: str = Field(..., description="The key to update.")
    value: str = Field(..., description="The value to store.")

class GitArgs(BaseModel):
    command: str = Field(..., description="Git subcommand: status, branch, commit, add, log.")
    message: Optional[str] = Field(None, description="Commit message if command is 'commit'.")

class DocSearchArgs(BaseModel):
    query: str = Field(..., description="The query to search for in the project documentation.")

class ClarificationArgs(BaseModel):
    question: str = Field(..., description="The question to ask the user for clarification.")

# Tool Implementations
def read_file(file_path: str) -> str:
    """Reads a file from the workspace."""
    try:
        p = Path(file_path).resolve()
        if not str(p).startswith(os.getcwd()):
            return "ERROR: Access denied. Path outside workspace."
        if not p.exists():
            return f"ERROR: File '{file_path}' not found."
        return p.read_text()
    except Exception as e:
        return f"ERROR: {e}"

def list_dir(dir_path: str = ".") -> str:
    """Lists files in a directory."""
    try:
        files = os.listdir(dir_path)
        return "\n".join(files)
    except Exception as e:
        return f"ERROR: {e}"

def write_file(file_path: str, content: str) -> str:
    """Writes content to a file in the workspace."""
    try:
        p = Path(file_path).resolve()
        # Security: Prevent writing outside workspace
        if not str(p).startswith(os.getcwd()):
            return "ERROR: Access denied. Path outside workspace."
        
        # Create parent directories if they don't exist
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"File '{file_path}' written successfully."
    except Exception as e:
        return f"ERROR: {e}"

async def shell_exec(command: str) -> str:
    """Executes a shell command."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip()
        err = stderr.decode().strip()
        if err:
            return f"STDOUT: {output}\nSTDERR: {err}"
        return output
    except Exception as e:
        return f"ERROR: {e}"

async def git_tool(command: str, message: Optional[str] = None) -> str:
    """Executes git commands."""
    try:
        cmd = ["git", command]
        if command == "commit" and message:
            cmd.extend(["-m", message])
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return (stdout.decode() + stderr.decode()).strip() or "Success"
    except Exception as e:
        return f"GIT ERROR: {e}"

async def doc_search(query: str) -> str:
    """Searches for a query in the project documentation (meta/dev/ directory)."""
    try:
        search_path = Path("meta/dev")
        if not search_path.exists():
            return "ERROR: meta/dev/ directory not found."
        
        # Simple grep-like search using asyncio
        process = await asyncio.create_subprocess_shell(
            f"grep -rnEi '{query}' meta/dev/",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip()
        if not output:
            return f"No results found for '{query}' in research/."
        return f"SEARCH RESULTS for '{query}':\n{output}"
    except Exception as e:
        return f"DOC SEARCH ERROR: {e}"

def request_clarification(question: str) -> str:
    """Pauses execution and asks the user for clarification."""
    # In a real environment, this might block or send a special signal.
    # Here, we return the question to the harness which can then prompt the user.
    return f"CLARIFICATION_REQUIRED: {question}"
