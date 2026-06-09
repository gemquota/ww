"""
AGENTS.md Hierarchical Instruction Loader.

Implements the industry-standard AGENTS.md format for project instructions,
compatible with Codex CLI, Claude Code, Aider, and other frontier tools.

Discovery order:
1. Global: ~/.ww/AGENTS.md (user-wide preferences)
2. Project root: ./AGENTS.md (project conventions)
3. Nested: subdirectory AGENTS.md files (override for specific areas)
"""

import os
from pathlib import Path
from typing import List, Optional

# Maximum combined instruction size (32 KiB, same as Codex CLI default)
MAX_INSTRUCTIONS_BYTES = 32 * 1024

# Filenames to search for (in priority order)
INSTRUCTION_FILENAMES = [
    "AGENTS.override.md",
    "AGENTS.md",
    "CLAUDE.md",       # Compatibility with Claude Code
    "GEMINI.md",       # Legacy compatibility with this project
    ".agents.md",
]


def get_global_instructions() -> Optional[str]:
    """
    Load global instructions from ~/.ww/AGENTS.md.

    These apply to every project and contain user-wide preferences.
    """
    home_dir = Path.home() / ".ww"
    if not home_dir.exists():
        return None

    for filename in INSTRUCTION_FILENAMES[:2]:  # Only AGENTS.override.md and AGENTS.md
        filepath = home_dir / filename
        if filepath.exists() and filepath.stat().st_size > 0:
            try:
                return filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
    return None


def get_project_instructions(workspace_root: Path) -> List[str]:
    """
    Load project instructions by walking from root to CWD.

    Implements Codex CLI's cascading discovery:
    - Start at project root (git root or workspace_root)
    - Walk down to CWD
    - At each level, check for instruction files in priority order
    - Include at most one file per directory
    """
    instructions = []
    total_bytes = 0

    # Find git root (if applicable)
    git_root = _find_git_root(workspace_root)
    start_dir = git_root if git_root else workspace_root

    # Walk from root to workspace_root (if they differ)
    dirs_to_check = _get_directory_chain(start_dir, workspace_root)

    for directory in dirs_to_check:
        for filename in INSTRUCTION_FILENAMES:
            filepath = directory / filename
            if filepath.exists() and filepath.stat().st_size > 0:
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    content_bytes = len(content.encode("utf-8"))

                    if total_bytes + content_bytes > MAX_INSTRUCTIONS_BYTES:
                        instructions.append(
                            f"[TRUNCATED: {filepath.name} exceeds instruction budget]"
                        )
                        return instructions

                    instructions.append(content)
                    total_bytes += content_bytes
                    break  # Only one file per directory
                except Exception:
                    continue

    return instructions


def load_all_instructions(workspace_root: Path) -> str:
    """
    Load and merge all instruction sources into a single string.

    Merge order (later content overrides earlier):
    1. Global ~/.ww/AGENTS.md
    2. Project root AGENTS.md
    3. Nested directory AGENTS.md files
    """
    parts = []

    # 1. Global instructions
    global_instr = get_global_instructions()
    if global_instr:
        parts.append(f"# Global Instructions (~/.ww/AGENTS.md)\n\n{global_instr}")

    # 2. Project instructions (cascading)
    project_instrs = get_project_instructions(workspace_root)
    if project_instrs:
        for i, instr in enumerate(project_instrs):
            parts.append(f"# Project Instructions (Level {i + 1})\n\n{instr}")

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)


def create_default_agents_md(workspace_root: Path) -> Path:
    """
    Create a default AGENTS.md file in the workspace root.

    This provides a starting template that users can customize.
    """
    agents_path = workspace_root / "AGENTS.md"
    if agents_path.exists():
        return agents_path

    template = """# AGENTS.md

## Project Overview
<!-- Describe your project here for AI agents -->

## Setup Commands
<!-- List commands to set up the development environment -->
- Install dependencies: `pip install -r requirements.txt`
- Run tests: `pytest`

## Code Style
- Follow PEP 8 for Python files
- Use type hints for function signatures
- Prefer explicit over implicit

## Testing Instructions
- Run the full test suite before committing
- Add tests for new functionality
- Ensure all tests pass: `pytest -v`

## Architecture Notes
<!-- Describe key architectural decisions -->

## Security Considerations
- Never commit secrets or API keys
- Validate all user inputs
- Use parameterized queries for databases
"""
    agents_path.write_text(template)
    return agents_path


def _find_git_root(start: Path) -> Optional[Path]:
    """Find the git repository root from a starting path."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    if (current / ".git").exists():
        return current
    return None


def _get_directory_chain(start: Path, end: Path) -> List[Path]:
    """Get the chain of directories from start to end (inclusive)."""
    start = start.resolve()
    end = end.resolve()

    if start == end:
        return [start]

    chain = [start]
    current = start

    # Walk from start toward end
    try:
        rel = end.relative_to(start)
        parts = rel.parts
        for part in parts:
            current = current / part
            chain.append(current)
    except ValueError:
        # end is not a subdirectory of start
        chain = [end]

    return chain
