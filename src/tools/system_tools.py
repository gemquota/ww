"""Tool implementations."""
import os
import asyncio
import shlex
import tempfile
import stat
from pathlib import Path
from typing import Optional


from src.tools.workspace import _get_workspace_root


def _resolve_workspace_path(path: str | Path) -> Path:
    """Resolve a path and reject anything outside the configured workspace."""
    root = _get_workspace_root().expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"Path is outside workspace: {path}") from exc
    return resolved


def _atomic_write_text(path: Path, content: str) -> None:
    """Replace a text file atomically, preserving existing mode where possible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".wwtmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


async def _read_capped_stream(reader, limit: int = 5 * 1024 * 1024) -> bytes:
    """Drain a subprocess pipe while retaining at most limit bytes."""
    chunks = []
    remaining = limit
    while chunk := await reader.read(65536):
        if remaining:
            kept = chunk[:remaining]
            chunks.append(kept)
            remaining -= len(kept)
    return b"".join(chunks)


async def _stop_process_group(process, streams_task) -> None:
    """Terminate a command and its descendants, then drain pipes and reap it."""
    import signal

    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        pass

    try:
        await asyncio.wait_for(asyncio.shield(streams_task), timeout=2)
    except asyncio.TimeoutError:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        await asyncio.gather(streams_task, return_exceptions=True)
    await process.wait()

async def _run_process(
    *command: str,
    shell: bool = False,
    cwd: str | Path | None = None,
    timeout: float = 60,
    output_limit: int = 5 * 1024 * 1024,
    env: dict[str, str] | None = None,
) -> tuple[bytes, bytes, int | None]:
    """Run a subprocess in its own process group with bounded capture and cleanup."""
    kwargs = {
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "cwd": str(cwd) if cwd is not None else None,
        "start_new_session": (os.name == "posix"),
        "env": env,
    }
    if shell:
        process = await asyncio.create_subprocess_shell(command[0], **kwargs)
    else:
        process = await asyncio.create_subprocess_exec(*command, **kwargs)

    stdout_task = asyncio.create_task(_read_capped_stream(process.stdout, output_limit))
    stderr_task = asyncio.create_task(_read_capped_stream(process.stderr, output_limit))
    streams_task = asyncio.gather(stdout_task, stderr_task)
    process_wait_task = asyncio.create_task(process.wait())
    completion = asyncio.gather(streams_task, process_wait_task)
    try:
        (stdout, stderr), returncode = await asyncio.wait_for(
            asyncio.shield(completion), timeout=timeout
        )
    except (asyncio.TimeoutError, asyncio.CancelledError):
        await _stop_process_group(process, streams_task)
        await asyncio.gather(completion, return_exceptions=True)
        raise
    return stdout, stderr, returncode


def _is_sensitive_workspace_path(path: Path) -> bool:
    """Avoid exposing common credential files through remote read tools."""
    protected_parts = {".git", ".ssh", ".aws", ".gnupg"}
    protected_names = {
        ".env", ".npmrc", "credentials", "secrets",
        "id_rsa", "id_ed25519",
    }
    lowered_parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        bool(lowered_parts & protected_parts)
        or name in protected_names
        or name.startswith(".env.")
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
    )


# Tool Implementations
def read_file(file_path: str) -> str:
    """Read a bounded UTF-8 text preview from a workspace file."""
    try:
        p = _resolve_workspace_path(file_path)
        if _is_sensitive_workspace_path(p):
            return "ERROR: Access denied. Sensitive files are not available through read tools."
        if not p.exists():
            return f"ERROR: File '{file_path}' not found."
        if not p.is_file():
            return f"ERROR: '{file_path}' is not a regular file."

        max_bytes = 128 * 1024
        max_lines = 500
        with p.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        byte_truncated = len(raw) > max_bytes
        raw = raw[:max_bytes]
        if b"\x00" in raw:
            return f"ERROR: '{file_path}' appears to be a binary file."
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        line_truncated = len(lines) > max_lines
        shown = lines[:max_lines]
        if not shown:
            preview = "(empty file)"
        else:
            preview = "\n".join(
                f"{index + 1:>5} | {line}" for index, line in enumerate(shown)
            )
        if byte_truncated or line_truncated:
            preview += (
                f"\n[TRUNCATED: preview limited to {max_bytes} bytes "
                f"and {max_lines} lines]"
            )
        return f"FILE: {p.relative_to(_get_workspace_root().resolve())}\n{preview}"
    except Exception as exc:
        return f"ERROR: {exc}"

def list_dir(dir_path: str = ".") -> str:
    try:
        p = _resolve_workspace_path(dir_path)
        files = os.listdir(p)
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

def write_file(file_path: str, content: str, permission_mgr=None, checkpoint_mgr=None, diff_engine=None) -> str:
    """Write content to a file with permission checks, checkpoints, and diffs."""
    from src.permissions import PermissionLevel
    try:
        p = _resolve_workspace_path(file_path)

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
        _atomic_write_text(p, content)

        if diff_engine and old_content and old_content != content:
            diff = diff_engine.colorize_diff(old_content, content, str(file_path))
            print(diff)

        # Syntax validation for Python files
        syntax_warning = ""
        if file_path.endswith('.py'):
            try:
                import py_compile as _py_compile
                _py_compile.compile(str(p), doraise=True)
            except _py_compile.PyCompileError as _e:
                syntax_warning = f"\n⚠ WARNING: Python syntax error: {_e}"
            except NameError:
                pass  # py_compile not available in some contexts
            except Exception:
                pass

        return f"SUCCESS: File '{file_path}' written ({len(content.encode('utf-8'))} bytes).{syntax_warning}"
    except Exception as e:
        return f"ERROR: {e}"

async def shell_exec(command: str, permission_mgr=None) -> str:
    """Execute a locally approved shell command with bounded output and cleanup."""
    from src.permissions import PermissionLevel

    try:
        if permission_mgr:
            perm = permission_mgr.classify_command(command)
            if perm == PermissionLevel.DENY:
                return f"DENIED: Command '{command}' is not allowed."
            if perm == PermissionLevel.ASK:
                from colorama import Fore, Style
                resp = input(
                    f"  {Fore.YELLOW}Request Approval: Run command "
                    f"'{command}' (y/n/always): {Style.RESET_ALL}"
                ).strip().lower()
                if resp not in {"y", "yes", "always"}:
                    return "DENIED: User rejected command execution."
                if resp == "always":
                    permission_mgr.always_allow.add(command)

        try:
            child_env = os.environ.copy()
            for secret_name in (
                "SECURE_1PSID", "SECURE_1PSIDTS", "GEMINI_API_KEY",
                "GOOGLE_API_KEY", "WW_DASHBOARD_API_KEY", "WW_DASHBOARD_API_KEYS",
            ):
                child_env.pop(secret_name, None)
            stdout, stderr, returncode = await _run_process(
                command, shell=True, cwd=_get_workspace_root(), timeout=60,
                env=child_env,
            )
        except asyncio.TimeoutError:
            return "ERROR: Command timed out after 60 seconds; process group terminated."

        output = stdout.decode(errors="replace")
        if stderr:
            output += f"\nSTDERR: {stderr.decode(errors='replace')}"
        output += f"\n[Exit code: {returncode}]"
        if len(output) > 10000:
            output = (
                output[:4000]
                + f"\n\n[... {len(output) - 8000} characters omitted ...]\n\n"
                + output[-4000:]
            )
        if len(stdout) >= 5 * 1024 * 1024 or len(stderr) >= 5 * 1024 * 1024:
            output += "\n[Output capture limited to 5 MiB per stream.]"
        return output or "(no output)"
    except Exception as exc:
        return f"ERROR: {exc}"


async def git_tool(command: str, message: Optional[str] = None) -> str:
    """Run a Git subcommand and arguments in the configured workspace."""
    try:
        parts = shlex.split(command)
        if not parts or any("\x00" in part for part in parts):
            return "GIT ERROR: A valid Git subcommand is required."
        cmd = ["git", *parts]
        if parts[0] == "commit" and message:
            cmd.extend(["-m", message])
        stdout, stderr, returncode = await _run_process(
            *cmd, cwd=_get_workspace_root(), timeout=120
        )
        combined = (stdout.decode(errors="replace") + stderr.decode(errors="replace")).strip()
        return f"{combined}\n[Exit code: {returncode}]" if combined else f"[Exit code: {returncode}]"
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

    results = []
    for sp in search_paths:
        try:
            stdout, stderr, _ = await _run_process(
                "grep", "-rnEi", "--include=*.md", "--", query, str(sp),
                cwd=_get_workspace_root(), timeout=15, output_limit=1024 * 1024,
            )
            out = stdout.decode(errors="replace").strip()
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
        search_path = _resolve_workspace_path(path)
        stdout, stderr, _ = await _run_process(
            "grep", "-rn", "--include=*.py", "--include=*.js", "--include=*.ts",
            "--include=*.md", "--include=*.json", "--include=*.yaml",
            "--include=*.yml", "--", pattern, str(search_path), cwd=_get_workspace_root(), timeout=30,
            output_limit=1024 * 1024,
        )
        out = stdout.decode(errors="replace").strip()
        if out:
            return f"CODE SEARCH RESULTS for '{pattern}':\n{out}"
        return f"No results found for '{pattern}'."
    except Exception as e:
        return f"CODE SEARCH ERROR: {e}"

def file_patch(file_path: str, search_text: str, replace_text: str, checkpoint_mgr=None, diff_engine=None) -> str:
    """Apply a surgical text replacement in a file with checkpoints and diffs."""
    try:
        p = _resolve_workspace_path(file_path)
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
            _atomic_write_text(p, new_content)
            # Syntax validation for Python files
            syntax_warning = ""
            if file_path.endswith('.py'):
                try:
                    import py_compile as _py_compile
                    _py_compile.compile(str(p), doraise=True)
                except _py_compile.PyCompileError as _e:
                    syntax_warning = f"\n⚠ WARNING: Python syntax error: {_e}"
                except Exception:
                    pass
            return f"SUCCESS: Patched '{file_path}' (1 replacement).{syntax_warning}"
    except Exception as e:
        return f"FILE PATCH ERROR: {e}"

async def url_fetch(url: str, timeout: int = 10) -> str:
    """Disabled until DNS pinning and redirect validation are implemented."""
    return (
        "URL FETCH DISABLED: network fetching is not exposed because the current "
        "urllib/curl implementation cannot reliably pin DNS results across redirects."
    )


if __name__ == "__main__":
    pass
