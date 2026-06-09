"""
Smart Context Gathering with Git-Awareness and Repo Mapping.

Enhanced workspace context engine that provides:
- .gitignore-aware file tree
- Intelligent file truncation (head + tail)
- AST-aware repository map for structural understanding
- Token-budget-aware context sizing
"""

import os
from pathlib import Path
from typing import List, Set, Optional
import pathspec

# Files that should almost always be included if they exist
CRITICAL_FILES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md",
    "package.json", "requirements.txt", "pyproject.toml",
    "Cargo.toml", "go.mod", ".env.example",
    "docker-compose.yml", "Dockerfile",
}

# Base directories and files to always ignore
BASE_IGNORE = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".ww", ".logs", "test_execution.log", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".next", ".nuxt",
}


def get_gitignore_spec(root: Path):
    """Loads .gitignore and returns a pathspec object."""
    gitignore = root / ".gitignore"
    patterns = []
    if gitignore.exists():
        try:
            patterns = gitignore.read_text().splitlines()
        except Exception:
            pass
    return pathspec.PathSpec.from_lines('gitwildmatch', patterns)


def is_binary(p: Path) -> bool:
    """Check if a file is likely binary."""
    try:
        with open(p, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True


def read_file_surgical(p: Path, max_lines: int = 150) -> str:
    """
    Reads a file with smart truncation (head and tail preservation).

    For log files, preserves the tail. For source files, preserves
    the head and tail with a truncation marker in the middle.
    """
    if is_binary(p):
        return f"[BINARY FILE: {p.name} - cannot display as text]"
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        if len(lines) <= max_lines:
            return "\n".join(lines)

        # For log files, show the tail
        if p.suffix in {".log", ".out"}:
            tail_lines = max_lines
            return (
                f"[... {len(lines) - tail_lines} lines omitted (showing tail) ...]\n"
                + "\n".join(lines[-tail_lines:])
            )

        # For source files, show head + tail
        half = max_lines // 2
        return (
            "\n".join(lines[:half])
            + f"\n\n[... {len(lines) - max_lines} lines truncated ...]\n\n"
            + "\n".join(lines[-half:])
        )
    except Exception as e:
        return f"[ERROR READING FILE: {e}]"


def get_directory_context(path: Path, depth: int = 2) -> str:
    """Gathers detailed context for a specific directory."""
    if not path.exists() or not path.is_dir():
        return f"ERROR: Directory {path} does not exist."

    tree_lines = [f"Detailed Structure for {path.name}/:"]
    for r, dirs, files in os.walk(path):
        rel_r = os.path.relpath(r, path)
        level = 0 if rel_r == "." else rel_r.count(os.sep) + 1
        if level > depth:
            continue

        dirs[:] = [d for d in dirs if d not in BASE_IGNORE]

        indent = "  " * level
        if rel_r != ".":
            tree_lines.append(f"{indent}{os.path.basename(r)}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            tree_lines.append(f"{sub_indent}{f}")

    return "\n".join(tree_lines)


def get_workspace_context(root_path: str = ".", max_tree_lines: int = 200) -> str:
    """
    Intelligently gathers workspace context using .gitignore and focused logic.

    Enhanced with:
    - Repo map integration for structural understanding
    - Token-aware sizing
    - Better file categorization
    """
    root = Path(root_path).resolve()
    spec = get_gitignore_spec(root)
    context_parts = []

    # 1. Critical configuration files (AGENTS.md, README, etc.)
    critical_content = []
    for cf in CRITICAL_FILES:
        p = root / cf
        if p.exists() and p.is_file():
            content = read_file_surgical(p, max_lines=100)
            critical_content.append(f"### {cf}\n```\n{content}\n```")

    if critical_content:
        context_parts.append(
            "## Critical Configuration & Metadata\n" + "\n\n".join(critical_content)
        )

    # 2. Optimized Tree (Respecting .gitignore)
    tree_lines = []
    for r, dirs, files in os.walk(root):
        rel_r = os.path.relpath(r, root)

        # Filter directories
        dirs[:] = sorted([
            d for d in dirs
            if d not in BASE_IGNORE and not spec.match_file(
                os.path.join(rel_r, d) if rel_r != "." else d
            )
        ])

        level = 0 if rel_r == "." else rel_r.count(os.sep) + 1
        indent = "  " * level
        if rel_r != ".":
            tree_lines.append(f"{indent}{os.path.basename(r)}/")

        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            rel_f = os.path.join(rel_r, f) if rel_r != "." else f
            if not spec.match_file(rel_f) and f not in BASE_IGNORE:
                tree_lines.append(f"{sub_indent}{f}")

        # Prevent tree from getting too large
        if len(tree_lines) > max_tree_lines:
            tree_lines.append(
                f"{sub_indent}... (tree truncated at {max_tree_lines} lines, "
                "use 'tool:list' or 'tool:focus' for details)"
            )
            break

    context_parts.append(
        "## Project Structure\n```\n" + "\n".join(tree_lines) + "\n```"
    )

    # 3. Repository Map (AST-aware symbols)
    try:
        from context_manager import RepoMapper
        mapper = RepoMapper(root, max_tokens=1500)
        repo_map = mapper.generate_map()
        if repo_map and len(repo_map) > 50:
            context_parts.append(f"## Repository Map\n```\n{repo_map}\n```")
    except ImportError:
        pass  # context_manager not available

    # 4. Git status (if available)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            context_parts.append(
                f"## Git Status (uncommitted changes)\n```\n{result.stdout.strip()}\n```"
            )

        # Recent commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=root, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            context_parts.append(
                f"## Recent Commits\n```\n{result.stdout.strip()}\n```"
            )
    except Exception:
        pass

    final_context = (
        "--- Workspace Context ---\n"
        "NOTE: This is a high-level summary. Use 'tool:read', 'tool:list', "
        "'tool:search', or 'tool:focus' to explore specific paths.\n\n"
        + "\n\n".join(context_parts)
        + "\n\n--- End Context ---\n"
    )
    return final_context
