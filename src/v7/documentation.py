"""V7-13: Documentation quality — API docs, diagram accuracy, consistency (Iris Fontaine)."""
from pathlib import Path
from typing import Dict, List, Optional
import ast
import re


class APIDocQuality:
    """Evaluate API documentation quality."""

    @staticmethod
    def check_docstring_coverage(root: Path) -> Dict:
        """Check what percentage of public functions have docstrings."""
        total_funcs = 0
        documented = 0
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        total_funcs += 1
                        if (node.body and isinstance(node.body[0], ast.Expr)
                                and isinstance(node.body[0].value, (ast.Constant))):
                            documented += 1
        return {
            "total_public_functions": total_funcs,
            "documented": documented,
            "coverage_pct": round(documented / max(total_funcs, 1) * 100, 1),
        }

    @staticmethod
    def check_param_docs(root: Path) -> List[Dict]:
        """Find functions with missing parameter documentation."""
        issues = []
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.args.args and not node.name.startswith("_"):
                        if (not node.body or not isinstance(node.body[0], ast.Expr)
                                or not isinstance(node.body[0].value, (ast.Constant))):
                            issues.append({
                                "file": rel,
                                "line": node.lineno,
                                "function": node.name,
                                "params": len(node.args.args),
                            })
        return issues[:20]


class DiagramAccuracy:
    """Check diagram references and accuracy."""

    @staticmethod
    def find_diagram_refs(root: Path) -> Dict:
        """Find references to diagrams in documentation."""
        refs = {"architecture_diagrams": [], "sequence_diagrams": [], "other": []}
        for mdfile in root.rglob("docs/**/*.md"):
            content = mdfile.read_text()
            for line in content.split("\n"):
                if "```" in line and ("mermaid" in line.lower() or "graph" in line.lower()):
                    refs["architecture_diagrams"].append(str(mdfile.relative_to(root)))
                if ".svg" in line or ".png" in line or ".drawio" in line:
                    refs["other"].append(str(mdfile.relative_to(root)))
        return {k: list(set(v)) for k, v in refs.items()}


class ConceptConsistency:
    """Check concept naming consistency across docs and code."""

    @staticmethod
    def check_terminology(root: Path) -> List[Dict]:
        """Find inconsistent terminology usage."""
        terms = {
            "Gemini Bridge": ["gemini_bridge", "ww", "bridge"],
            "Overseer": ["overseer", "manager", "controller"],
        }
        issues = []
        for mdfile in root.rglob("docs/**/*.md"):
            content = mdfile.read_text()
            rel = str(mdfile.relative_to(root))
            for canonical, aliases in terms.items():
                for alias in aliases:
                    if alias.lower() != canonical.lower() and alias.lower() in content.lower():
                        issues.append({
                            "file": rel,
                            "canonical": canonical,
                            "alias_found": alias,
                        })
        return issues[:20]
