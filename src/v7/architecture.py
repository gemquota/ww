"""V7-01: Architecture modularity & dependency management (Marcus Chen)."""
import ast
from pathlib import Path
from typing import List, Dict, Set, Tuple

class ModularityChecker:
    """Check module boundaries and dependency hygiene."""

    FORBIDDEN_CROSS_IMPORTS = {
        "src.dashboard": ["src.core", "src.tools"],
        "src.tools": ["src.dashboard"],
        "src.plugins": ["src.dashboard"],
    }

    def __init__(self, root: Path):
        self.root = root.resolve()

    def check_layer_violations(self) -> List[Dict]:
        """Find cross-layer import violations."""
        violations = []
        for src_dir, forbidden in self.FORBIDDEN_CROSS_IMPORTS.items():
            for pyfile in sorted((self.root / src_dir.replace(".", "/")).rglob("*.py")):
                if pyfile.name == "__init__.py":
                    continue
                content = pyfile.read_text()
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            for fb in forbidden:
                                if alias.name.startswith(fb):
                                    violations.append({
                                        "file": str(pyfile.relative_to(self.root)),
                                        "line": node.lineno,
                                        "import": alias.name,
                                        "forbidden_by": fb,
                                    })
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and any(node.module.startswith(fb) for fb in forbidden):
                            violations.append({
                                "file": str(pyfile.relative_to(self.root)),
                                "line": node.lineno,
                                "import": f"from {node.module} import ...",
                                "forbidden_by": next(fb for fb in forbidden if node.module.startswith(fb)),
                            })
        return violations

    def check_abstraction_boundaries(self) -> List[Dict]:
        """Check that internal details aren't imported from outside."""
        issues = []
        internal_modules = ["src.core", "src.tools", "src.utils"]
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            content = pyfile.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            if any(rel.startswith(m.replace(".", "/")) for m in internal_modules):
                continue  # Skip internal modules
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if any(node.module.startswith(im) for im in internal_modules):
                        issues.append({
                            "file": rel,
                            "line": node.lineno,
                            "import": node.module,
                            "note": "Direct import of internal module",
                        })
        return issues

    def report(self) -> Dict:
        return {
            "layer_violations": self.check_layer_violations(),
            "abstraction_violations": self.check_abstraction_boundaries(),
            "score": 100 - len(self.check_layer_violations()) * 10,
        }


class DependencyGraph:
    """Analyze and visualize dependency relationships."""

    def __init__(self, root: Path):
        self.root = root
        self._graph: Dict[str, Set[str]] = {}

    def build(self) -> Dict[str, Set[str]]:
        """Build the dependency graph from all src files."""
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            self._graph.setdefault(rel, set())
            content = pyfile.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._graph[rel].add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    self._graph[rel].add(node.module.split(".")[0])
        return self._graph

    def find_cycles(self) -> List[Set[str]]:
        """Find circular dependencies."""
        if not self._graph:
            self.build()
        visited: Set[str] = set()
        path: List[str] = []
        cycles: List[Set[str]] = []

        def dfs(node: str):
            if node in path:
                cycle = path[path.index(node):]
                cycles.append(set(cycle))
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in self._graph.get(node, set()):
                if neighbor in self._graph:
                    dfs(neighbor)
            path.pop()

        for node in list(self._graph.keys()):
            if node not in visited:
                dfs(node)

        return cycles

    def get_fan_in_out(self, module: str) -> Dict:
        """Get fan-in (dependents) and fan-out (dependencies) for a module."""
        if not self._graph:
            self.build()
        fan_out = len(self._graph.get(module, set()))
        fan_in = sum(1 for deps in self._graph.values() if module in deps)
        return {"module": module, "fan_in": fan_in, "fan_out": fan_out}
