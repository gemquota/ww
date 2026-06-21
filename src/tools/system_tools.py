"""Tool implementations."""
import os
import subprocess
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

from src.tools.args import (
    ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs,
    UpdateScratchpadArgs, GitArgs, DocSearchArgs, ClarificationArgs,
    CodeSearchArgs, FilePatchArgs, UrlFetchArgs,
)


from src.tools.workspace import _get_workspace_root, set_workspace_root


# Tool Implementations
def read_file(file_path: str) -> str:
    """Read a file using surgical truncation if it's too large."""
    from src.smart_context import read_file_surgical
    p = Path(file_path).resolve()
    root = _get_workspace_root()
    try:
        if not str(p).startswith(str(root)):
            return f"ERROR: Access denied. Path '{file_path}' is outside workspace."
        if not p.exists():
            return f"ERROR: File '{file_path}' not found."
        return read_file_surgical(p, max_lines=500)
    except Exception as e:
        return f"ERROR: {e}"

def list_dir(dir_path: str = ".") -> str:
    try:
        p = Path(dir_path).resolve()
        root = _get_workspace_root()
        if not str(p).startswith(str(root)):
             return f"ERROR: Access denied. Path '{dir_path}' is outside workspace."
        files = os.listdir(dir_path)
        entries = []
        for f in sorted(files):
            full = p / f
            suffix = "/" if full.is_dir() else ""
            entries.append(f"{f}{suffix}")
        return "\n".join(entries) or "(empty directory)"
    except PermissionError:
        return f"ERROR: Permission denied listing '{dir_path}'."
    except Exception as e:
        return f"ERROR: {e}"

async def write_file(file_path: str, content: str, permission_mgr=None, checkpoint_mgr=None, diff_engine=None) -> str:
    """Write content to a file with permission checks, checkpoints, and diffs."""
    from src.permissions import PermissionLevel
    try:
        p = Path(file_path).resolve()
        root = _get_workspace_root()
        if not str(p).startswith(str(root)):
            return f"ERROR: Access denied. Path '{file_path}' is outside workspace."

        if permission_mgr:
            perm = permission_mgr.classify_write(str(file_path))
            if perm == PermissionLevel.DENY:
                return f"DENIED: Cannot write to protected path '{file_path}'."
            if perm == PermissionLevel.ASK:
                from colorama import Fore, Style
                resp = input(f"  {Fore.YELLOW}Request Approval: Write to {file_path} (y/n): {Style.RESET_ALL}").lower()
                if resp != "y":
                    return "DENIED: User rejected file write."

        if checkpoint_mgr:
            cp_id = checkpoint_mgr.create_checkpoint(f"write:{file_path}")
            if p.exists():
                checkpoint_mgr.save_file_state(p, cp_id)

        old_content = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        if diff_engine and old_content and old_content != content:
            diff = diff_engine.colorize_diff(old_content, content, str(file_path))
            print(diff)

        # Syntax validation for Python files
        syntax_warning = ""
        if file_path.endswith('.py'):
            try:
                import py_compile as _py_compile
                _py_compile.compile(file_path, doraise=True)
            except py_compile.PyCompileError as _e:
                syntax_warning = f"\n⚠ WARNING: Python syntax error: {_e}"
            except NameError:
                pass  # py_compile not available in some contexts
            except Exception:
                pass

        return f"SUCCESS: File '{file_path}' written ({len(content)} bytes).{syntax_warning}"
    except Exception as e:
        return f"ERROR: {e}"

async def shell_exec(command: str, permission_mgr=None) -> str:
    """Execute a shell command with permission checks and resource limits."""
    from src.permissions import PermissionLevel
    
    # Define resource limits (applied per-call, restored afterward)
    _RLIMITS = {
        "RLIMIT_CPU": 30,      # 30 seconds CPU time
        "RLIMIT_AS": 256 * 1024 * 1024,      # 256MB virtual memory
        "RLIMIT_NOFILE": 128,  # Max open file descriptors
    }
    
    try:
        if permission_mgr:
            perm = permission_mgr.classify_command(command)
            if perm == PermissionLevel.DENY:
                return f"DENIED: Command '{command}' is not allowed."
            if perm == PermissionLevel.ASK:
                from colorama import Fore, Style
                resp = input(f"  {Fore.YELLOW}Request Approval: Run command '{command}' (y/n/always): {Style.RESET_ALL}").lower()
                if resp == "n":
                    return "DENIED: User rejected command execution."
                elif resp == "always":
                    permission_mgr.always_allow.add(command)
        
        # Apply resource limits with save/restore
        import resource
        _saved_limits = {}
        for _rl_name, _rl_value in _RLIMITS.items():
            _rl_const = getattr(resource, _rl_name, None)
            if _rl_const is not None:
                try:
                    _saved_limits[_rl_const] = resource.getrlimit(_rl_const)
                    resource.setrlimit(_rl_const, (_rl_value, _rl_value))
                except (ValueError, resource.error):
                    pass  # Silently skip limits that can't be set in this environment
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_get_workspace_root())
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
        finally:
            # Restore original resource limits
            for _rl_const, _saved in _saved_limits.items():
                try:
                    resource.setrlimit(_rl_const, _saved)
                except Exception:
                    pass
        
        output = ""
        if stdout:
            output += stdout.decode(errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode(errors='replace')}"
        if process.returncode != 0:
            output += f"\n[Exit code: {process.returncode}]"

        if len(output) > 10000:
            output = output[:4000] + f"\n\n[... {len(output) - 8000} chars truncated ...]\n\n" + output[-4000:]
        return output or "(no output)"
    except asyncio.TimeoutError:
        return "ERROR: Command timed out after 60 seconds."
    except Exception as e:
        return f"ERROR: {e}"

async def git_tool(command: str, message: Optional[str] = None) -> str:
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
    """Search project documentation in docs/ and meta/ directories."""
    search_paths = []
    for sp in [Path("docs"), Path("meta")]:
        if sp.exists():
            search_paths.append(sp)
    if not search_paths:
        return "ERROR: No documentation directories (docs/ or meta/) found."

    import shlex
    safe_query = shlex.quote(query)
    results = []
    for sp in search_paths:
        try:
            proc = await asyncio.create_subprocess_shell(
                f"grep -rnEi {safe_query} {sp}/ --include='*.md' 2>/dev/null | head -40",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode().strip()
            if out:
                results.append(f"[{sp}/]\n{out}")
        except Exception:
            continue

    if not results:
        return f"No documentation results found for '{query}'."
    return f"DOCUMENTATION SEARCH RESULTS for '{query}':\n\n" + "\n\n".join(results)

def request_clarification(question: str) -> str:
    return f"CLARIFICATION_REQUIRED: {question}"

# ── New Tool Implementations (Set 3) ──

async def code_search(pattern: str, path: str = ".") -> str:
    """Search for a pattern across project files using grep."""
    try:
        proc = await asyncio.create_subprocess_shell(
            f"grep -rn '{pattern}' {path} --include='*.py' --include='*.js' --include='*.ts' --include='*.md' --include='*.json' --include='*.yaml' --include='*.yml' 2>/dev/null | head -40",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode().strip()
        if out:
            return f"CODE SEARCH RESULTS for '{pattern}':\n{out}"
        return f"No results found for '{pattern}'."
    except Exception as e:
        return f"CODE SEARCH ERROR: {e}"

async def file_patch(file_path: str, search_text: str, replace_text: str, checkpoint_mgr=None, diff_engine=None) -> str:
    """Apply a surgical text replacement in a file with checkpoints and diffs."""
    try:
        p = Path(file_path).resolve()
        root = _get_workspace_root()
        if not str(p).startswith(str(root)):
            return "ERROR: Access denied. Path outside workspace."
        if not p.exists():
            return f"ERROR: File '{file_path}' not found."

        if checkpoint_mgr:
            cp_id = checkpoint_mgr.create_checkpoint(f"patch:{file_path}")
            checkpoint_mgr.save_file_state(p, cp_id)

        content = p.read_text(encoding="utf-8", errors="replace")
        if search_text not in content:
            return f"ERROR: Search text not found in '{file_path}'."

        if diff_engine:
            success, message, diff_output = diff_engine.apply_edit(p, search_text, replace_text)
            if success and diff_output:
                print(diff_output)
            return message
        else:
            new_content = content.replace(search_text, replace_text, 1)
            p.write_text(new_content, encoding="utf-8")
            # Syntax validation for Python files
            syntax_warning = ""
            if file_path.endswith('.py'):
                try:
                    import py_compile as _py_compile
                    _py_compile.compile(file_path, doraise=True)
                except py_compile.PyCompileError as _e:
                    syntax_warning = f"\n⚠ WARNING: Python syntax error: {_e}"
                except Exception:
                    pass
            return f"SUCCESS: Patched '{file_path}' (1 replacement).{syntax_warning}"
    except Exception as e:
        return f"FILE PATCH ERROR: {e}"

def _is_safe_url(url: str) -> str:
    """Validate URL for SSRF safety. Returns error message or empty string."""
    from urllib.parse import urlparse
    import ipaddress
    try:
        parsed = urlparse(url)
    except Exception:
        return "SSRF ERROR: Invalid URL format"
    if parsed.scheme not in ("http", "https"):
        return f"SSRF ERROR: Scheme '{parsed.scheme}' not allowed (only http/https)"
    if parsed.port is not None and parsed.port not in (80, 443):
        return f"SSRF ERROR: Port {parsed.port} not allowed (only 80/443)"
    host = parsed.hostname
    if not host:
        return "SSRF ERROR: No hostname in URL"
    try:
        import socket
        addr = socket.getaddrinfo(host, parsed.port or 443, socket.AF_INET)[0][4][0]
        ip = ipaddress.ip_address(addr)
        if ip.is_private:
            return f"SSRF ERROR: Private IP range not allowed ({addr})"
        if ip.is_loopback:
            return f"SSRF ERROR: Loopback address not allowed ({addr})"
        if ip.is_link_local:
            return f"SSRF ERROR: Link-local address not allowed ({addr})"
        if ip.is_multicast:
            return f"SSRF ERROR: Multicast address not allowed ({addr})"
        if ip.is_reserved:
            return f"SSRF ERROR: Reserved address not allowed ({addr})"
    except socket.gaierror:
        return ""  # DNS resolution failed — let fetch attempt handle it
    except Exception as e:
        return f"SSRF ERROR: Address validation failed ({e})"
    return ""  # URL is safe


async def url_fetch(url: str, timeout: int = 10) -> str:
    """Fetch a URL via HTTP GET with timeout. Uses urllib with curl fallback."""
    # SSRF protection — validate URL before fetching
    ssrf_error = _is_safe_url(url)
    if ssrf_error:
        return ssrf_error
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "WW-Bridge/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode(errors="replace")
            return data[:5000] + ("\n[... truncated ...]" if len(data) > 5000 else "")
    except Exception as e:
        # Fallback: try curl
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-s", "--max-time", str(timeout), "-L", url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode().strip()
            if out:
                return out[:5000] + ("\n[... truncated ...]" if len(out) > 5000 else "")
            err = stderr.decode().strip()
            return f"URL FETCH ERROR: {err or 'Empty response'}"
        except FileNotFoundError:
            return "URL FETCH ERROR: Neither urllib nor curl available for HTTP requests."
        except Exception as e2:
            return f"URL FETCH ERROR: {e2}"


if __name__ == "__main__":
    pass
