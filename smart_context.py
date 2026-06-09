import os
from pathlib import Path
from typing import List, Set
import pathspec

# Files that should almost always be included if they exist
CRITICAL_FILES = {
    "GEMINI.md", "README.md", "package.json", "requirements.txt", 
    "pyproject.toml", "Cargo.toml", "go.mod", ".env.example",
    "docker-compose.yml", "Dockerfile"
}

# Base directories to always ignore
BASE_IGNORE = {".git", "node_modules", "__pycache__", "venv", ".venv"}

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

def get_workspace_context(root_path: str = ".") -> str:
    """
    Intelligently gathers workspace context using .gitignore and focused logic.
    """
    root = Path(root_path).resolve()
    spec = get_gitignore_spec(root)
    context_parts = []
    
    # 1. Critical configuration files
    critical_content = []
    for cf in CRITICAL_FILES:
        p = root / cf
        if p.exists() and p.is_file():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                critical_content.append(f"File: {cf}\n---\n{content}\n")
            except Exception:
                pass
    
    if critical_content:
        context_parts.append("### Critical Configuration & Metadata\n" + "\n".join(critical_content))

    # 2. Optimized Tree (Respecting .gitignore)
    tree_lines = ["Workspace Structure (filtered):"]
    for r, dirs, files in os.walk(root):
        rel_r = os.path.relpath(r, root)
        
        # Filter directories
        dirs[:] = [d for d in dirs if d not in BASE_IGNORE and not spec.match_file(os.path.join(rel_r, d))]
        
        level = 0 if rel_r == "." else rel_r.count(os.sep) + 1
        indent = "  " * level
        if rel_r != ".":
            tree_lines.append(f"{indent}📁 {os.path.basename(r)}/")
        
        sub_indent = "  " * (level + 1)
        for f in sorted(files):
            rel_f = os.path.join(rel_r, f) if rel_r != "." else f
            if not spec.match_file(rel_f):
                tree_lines.append(f"{sub_indent}📄 {f}")
                
        # Prevent tree from getting too large for massive monorepos
        if len(tree_lines) > 200:
            tree_lines.append(f"{sub_indent}... (tree truncated, use 'tool:list' for more details)")
            break

    context_parts.append("### Project Structure\n```text\n" + "\n".join(tree_lines) + "\n```")

    final_context = (
        "--- Relevant Workspace Context ---\n"
        "NOTE: This is a high-level summary. Use the 'read', 'list', or 'search' tools to explore deep paths.\n\n"
        + "\n\n".join(context_parts) + 
        "\n---------------------------------\n"
    )
    return final_context
