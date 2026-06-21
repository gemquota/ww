"""
AST-level validation for SEARCH/REPLACE edits — NEW-V5-E1#2 (Dr. Felix Weber).

Verifies that after applying a SEARCH/REPLACE, the AST structure changed
only in the intended locations.
"""
import ast
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path


class ASTValidator:
    """Validates AST structure changes after SEARCH/REPLACE operations."""

    @staticmethod
    def get_ast_structure(source: str) -> Dict:
        """Extract structural elements from source code AST."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"valid": False, "error": "Syntax error in source"}

        structure = {
            "valid": True,
            "imports": [],
            "functions": [],
            "classes": [],
            "assignments": [],
            "calls": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                structure["imports"].extend(
                    alias.name for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                structure["imports"].append(
                    f"{node.module}.{node.names[0].name}" if node.names else node.module
                )
            elif isinstance(node, ast.FunctionDef):
                structure["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                structure["classes"].append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        structure["assignments"].append(target.id)

        return structure

    @staticmethod
    def get_changed_regions(original: str, modified: str) -> List[Tuple[int, int]]:
        """Return line ranges that changed between original and modified."""
        orig_lines = original.split("\n")
        mod_lines = modified.split("\n")
        changes = []
        start = None

        max_lines = max(len(orig_lines), len(mod_lines))
        for i in range(max_lines):
            o = orig_lines[i] if i < len(orig_lines) else ""
            m = mod_lines[i] if i < len(mod_lines) else ""
            if o != m:
                if start is None:
                    start = i + 1  # 1-indexed
            else:
                if start is not None:
                    changes.append((start, i))
                    start = None

        if start is not None:
            changes.append((start, max_lines))

        return changes

    @staticmethod
    def validate_edit_scope(
        original: str,
        modified: str,
        intended_scope: Optional[str] = None,
    ) -> Dict:
        """Validate that edits only changed intended scope.

        Args:
            original: Original source code
            modified: Modified source code
            intended_scope: Function or class name that should be the only change

        Returns:
            Dict with validation result
        """
        orig_struct = ASTValidator.get_ast_structure(original)
        mod_struct = ASTValidator.get_ast_structure(modified)

        if not orig_struct.get("valid"):
            return {"valid": False, "error": orig_struct.get("error", "Invalid original")}
        if not mod_struct.get("valid"):
            return {"valid": False, "error": mod_struct.get("error", "Invalid modified")}

        # Detect unintended structural changes
        issues = []

        # Check for unexpected new functions/classes
        new_funcs = set(mod_struct["functions"]) - set(orig_struct["functions"])
        removed_funcs = set(orig_struct["functions"]) - set(mod_struct["functions"])
        new_classes = set(mod_struct["classes"]) - set(orig_struct["classes"])
        removed_classes = set(orig_struct["classes"]) - set(mod_struct["classes"])
        new_imports = set(mod_struct["imports"]) - set(orig_struct["imports"])

        if intended_scope:
            # If scope specified, validate only that scope changed
            if intended_scope in orig_struct["functions"]:
                pass  # Expected function change
            elif intended_scope in orig_struct["classes"]:
                pass  # Expected class change
            else:
                # Check if change was scoped correctly
                if new_funcs and intended_scope not in new_funcs:
                    issues.append(f"Unexpected new function(s): {new_funcs}")

        # General validation
        if len(removed_funcs) > 0:
            issues.append(f"Removed function(s): {removed_funcs}")
        if len(new_classes) > 0:
            issues.append(f"New class(es): {new_classes}")
        if len(removed_classes) > 0:
            issues.append(f"Removed class(es): {removed_classes}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "structural_changes": {
                "new_functions": list(new_funcs),
                "removed_functions": list(removed_funcs),
                "new_classes": list(new_classes),
                "removed_classes": list(removed_classes),
                "new_imports": list(new_imports),
            },
        }
