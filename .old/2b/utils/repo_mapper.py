import os
from pathlib import Path
from typing import List, Optional

class RepoMapper:
    """
    Generates a structural map of the repository to provide high-level context.
    """
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root

    def generate_map(self, max_depth: int = 2) -> str:
        """
        Returns a tree-like string of the workspace structure.
        """
        map_parts = ["REPOSITORY STRUCTURE:"]
        
        def _walk(current_path: Path, depth: int):
            if depth > max_depth:
                return
            
            try:
                # Filter out hidden and common ignored dirs
                items = sorted([
                    item for item in current_path.iterdir()
                    if not item.name.startswith('.') and item.name not in {'__pycache__', 'node_modules', 'venv'}
                ])
                
                for item in items:
                    indent = "  " * (depth + 1)
                    if item.is_dir():
                        map_parts.append(f"{indent}📁 {item.name}/")
                        _walk(item, depth + 1)
                    else:
                        map_parts.append(f"{indent}📄 {item.name}")
            except Exception:
                pass

        _walk(self.workspace_root, 0)
        return "\n".join(map_parts)
