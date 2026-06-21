"""V7-06: Maintainability — config fragmentation, god object, coupling (Yuki Tanaka)."""
import ast
from pathlib import Path
from typing import List, Dict, Set, Any


class ConfigAnalyzer:
    """Analyze configuration fragmentation across the codebase."""

    @staticmethod
    def find_config_sources(root: Path) -> List[Dict]:
        """Find all configuration reading sites."""
        sources = []
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            for i, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if any(w in stripped for w in ["os.getenv(", "os.environ.get", "config(", "getenv("]):
                    if "os.getenv(" in stripped or "os.environ.get" in stripped:
                        sources.append({"file": rel, "line": i, "type": "env_var", "context": stripped[:80]})
                    elif "config(" in stripped.lower() or "get_config" in stripped:
                        sources.append({"file": rel, "line": i, "type": "config_call", "context": stripped[:80]})
        return sources

    def report(self, root: Path) -> Dict[str, Any]:
        sources = self.find_config_sources(root)
        return {
            "total_config_sources": len(sources),
            "env_var_accesses": len([s for s in sources if s["type"] == "env_var"]),
            "config_calls": len([s for s in sources if s["type"] == "config_call"]),
            "sources": sources[:20],
        }


class GodObjectDetector:
    """Detect god objects — modules with too many responsibilities."""

    RESPONSIBILITY_KEYWORDS = {
        "read", "write", "parse", "validate", "transform", "dispatch",
        "execute", "monitor", "log", "cache", "sync", "notify",
        "serialize", "deserialize", "render", "format", "convert",
        "initialize", "cleanup", "rollback", "checkpoint", "recover",
    }

    def __init__(self, threshold: int = 8):
        self.threshold = threshold

    def scan_module(self, pyfile: Path) -> Dict:
        """Count distinct responsibilities in a module."""
        content = pyfile.read_text()
        rel = str(pyfile.name)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"file": rel, "responsibilities": 0, "is_god_object": False, "funcs": []}

        funcs = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        responsibilities = set()
        for func in funcs:
            for kw in self.RESPONSIBILITY_KEYWORDS:
                if kw in func.lower():
                    responsibilities.add(kw)

        is_god = len(responsibilities) >= self.threshold
        return {
            "file": rel,
            "responsibilities": len(responsibilities),
            "is_god_object": is_god,
            "func_count": len(funcs),
            "funcs": funcs[:15],
        }

    def scan_all(self, root: Path) -> List[Dict]:
        results = []
        for pyfile in sorted(root.rglob("src/**/*.py")):
            if pyfile.name == "__init__.py":
                continue
            results.append(self.scan_module(pyfile))
        return [r for r in results if r["is_god_object"]]


class CouplingAnalyzer:
    """Measure feature coupling between modules."""

    def __init__(self, root: Path):
        self.root = root

    def measure_coupling(self) -> Dict[str, Any]:
        """Measure import coupling between modules."""
        modules = {}
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            content = pyfile.read_text()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 2:
                        imports.add(f"{parts[0]}.{parts[1]}")
            modules[rel] = imports

        # Find shared import patterns (coupling)
        coupling_pairs = []
        mod_list = list(modules.keys())
        for i in range(len(mod_list)):
            for j in range(i + 1, len(mod_list)):
                shared = modules[mod_list[i]] & modules[mod_list[j]]
                if len(shared) >= 3:
                    coupling_pairs.append({
                        "module_a": mod_list[i],
                        "module_b": mod_list[j],
                        "shared_imports": len(shared),
                        "imports": list(shared),
                    })

        return {
            "total_modules": len(modules),
            "highly_coupled_pairs": len([p for p in coupling_pairs if p["shared_imports"] >= 5]),
            "coupling_pairs": sorted(coupling_pairs, key=lambda x: -x["shared_imports"])[:10],
        }
