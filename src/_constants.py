"""
Shared constants for WW Bridge.

Single source of truth for ignore sets, critical file lists, and
workspace-wide configuration defaults used across multiple modules.
"""

# Files that should almost always be included in workspace context
CRITICAL_FILES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md",
    "package.json", "requirements.txt", "pyproject.toml",
    "Cargo.toml", "go.mod", ".env.example",
    "docker-compose.yml", "Dockerfile",
}

# Base directories and files to always ignore during workspace walks
BASE_IGNORE = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    ".ww", ".logs", "test_execution.log", ".mypy_cache",
    ".pytest_cache", "dist", "build", ".next", ".nuxt",
}

# File extensions that can be parsed for structural symbols
PARSEABLE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java"}

# Default file read truncation limits (lines)
MAX_FILE_LINES_DEFAULT = 150
MAX_FILE_LINES_CRITICAL = 100
MAX_FILE_LINES_AGENTS = 400
MAX_TREE_LINES = 200
