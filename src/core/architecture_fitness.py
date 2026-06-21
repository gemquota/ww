"""Architecture fitness functions — automated architectural constraint validation."""
import ast
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple


class ArchitectureFitness:
    """Evaluates architectural fitness functions across the codebase."""

    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()

    def check_layer_violations(self) -> List[Tuple[str, str, str]]:
        """Detect imports that cross architectural layer boundaries.
        Returns list of (source_file, imported_module, violation_type)."""
        violations = []
        layer_map = {
            "src/core": {"layer": "core", "allowed_deps": {"src/core", "pydantic", "sqlite3", "pathlib", "typing"}},
            "src/tools": {"layer": "tools", "allowed_deps": {"src/core", "src/tools", "src/utils", "pydantic", "pathlib"}},
            "src/utils": {"layer": "utils", "allowed_deps": {"src/core", "pydantic"}},
            "src/dashboard": {"layer": "dashboard", "allowed_deps": {"src/core", "src/tools", "fastapi"}},
            "src": {"layer": "bridge", "allowed_deps": {"src/core", "src/tools", "src/utils", "src/dashboard"}},
        }

        for pyfile in self.root.rglob("src/**/*.py"):
            if pyfile.name == "__init__.py":
                continue
            rel = str(pyfile.relative_to(self.root))
            try:
                tree = ast.parse(pyfile.read_text())
            except SyntaxError:
                continue

            # Determine layer
            file_layer = None
            for prefix, info in layer_map.items():
                if rel.startswith(prefix):
                    file_layer = info["layer"]
                    break
            if not file_layer:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._check_import(rel, alias.name, file_layer, layer_map, violations)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self._check_import(rel, node.module, file_layer, layer_map, violations)
        return violations

    def _check_import(self, source: str, imported: str, file_layer: str,
                      layer_map: dict, violations: list):
        if imported.startswith("src."):
            imported_pkg = imported.replace(".", "/", 1)
            for prefix, info in layer_map.items():
                if imported_pkg.startswith(prefix):
                    imported_layer = info["layer"]
                    if imported_layer not in [d.replace("src/", "src.", 1).replace("/", ".") for d in info["allowed_deps"]]:
                        if imported_layer != file_layer:  # Cross-layer
                            violations.append((source, imported, f"{file_layer}→{imported_layer}"))

    def check_abstract_dependency_ratio(self) -> float:
        """Calculate ratio of abstract (interface) vs concrete modules."""
        abstract = 0
        concrete = 0
        for pyfile in self.root.rglob("src/**/*.py"):
            if pyfile.name.startswith("_") or pyfile.name == "__init__.py":
                continue
            text = pyfile.read_text()
            if "class ABC" in text or "Protocol" in text or "abstractmethod" in text or "Interface" in text:
                abstract += 1
            else:
                concrete += 1
        total = abstract + concrete
        return abstract / total if total > 0 else 0

    def get_component_boundaries(self) -> Dict[str, Set[str]]:
        """Map each component to its set of exposed (public) symbols."""
        boundaries = {}
        for pyfile in sorted(self.root.rglob("src/**/__init__.py")):
            component = str(pyfile.parent.relative_to(self.root))
            text = pyfile.read_text()
            exports = set()
            for match in re.finditer(r'__all__\s*=\s*\[([^\]]+)\]', text):
                exports.update(re.findall(r"'([^']+)'", match.group(1)))
            for match in re.finditer(r'from\s+\.\w+\s+import\s+(.+)$', text, re.MULTILINE):
                for name in re.findall(r'\b([A-Z]\w+)\b', match.group(1)):
                    exports.add(name)
            boundaries[component] = exports
        return boundaries

    def check_boundary_discipline(self) -> List[str]:
        """Check that internal symbols aren't imported across component boundaries."""
        issues = []
        boundaries = self.get_component_boundaries()
        for pyfile in self.root.rglob("src/**/*.py"):
            if pyfile.name == "__init__.py":
                continue
            rel = str(pyfile.relative_to(self.root))
            text = pyfile.read_text()
            for comp, exports in boundaries.items():
                if rel.startswith(comp):
                    continue  # Same component, allowed
                for symbol in exports:
                    if symbol in text and f"import {symbol}" in text:
                        issues.append(f"{rel} imports '{symbol}' from {comp}")
        return issues
