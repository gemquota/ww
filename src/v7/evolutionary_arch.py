"""V7-04: Evolutionary Architecture — DI, build modularity, fitness (Dr. Kira Ivanova)."""
import ast
from pathlib import Path
from typing import Dict, List, Any


class DependencyInjectionChecker:
    """Check dependency injection patterns."""

    @staticmethod
    def scan_for_di_patterns(root: Path) -> Dict:
        """Scan for DI-related patterns in the codebase."""
        results = {"hardcoded_instantiations": 0, "constructor_injection": 0, "files": []}
        for pyfile in root.rglob("src/**/*.py"):
            content = pyfile.read_text()
            rel = str(pyfile.relative_to(root))
            file_results = {"file": rel, "issues": []}
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                            for stmt in ast.walk(item):
                                if isinstance(stmt, ast.Assign):
                                    for target in stmt.targets:
                                        if isinstance(target, ast.Attribute) and isinstance(stmt.value, ast.Call):
                                            if not isinstance(stmt.value.func, ast.Name) or stmt.value.func.id not in ("None", "False", "True"):
                                                results["hardcoded_instantiations"] += 1
                                                file_results["issues"].append({
                                                    "line": stmt.lineno,
                                                    "pattern": "hardcoded_instantiation",
                                                    "detail": f"{ast.dump(stmt.value.func)[:40] if hasattr(stmt.value, 'func') else 'Call'}"
                                                })
            if file_results["issues"]:
                results["files"].append(file_results)
        return results


class BuildModularity:
    """Analyze build system modularity."""

    @staticmethod
    def check_build_files(root: Path) -> Dict:
        build_files = []
        for pattern in ["*.toml", "Makefile", "*.cfg", "pyproject.toml"]:
            build_files.extend(root.glob(pattern))
        return {
            "build_files_found": len(build_files),
            "files": [str(f.relative_to(root)) for f in build_files],
        }


class FitnessFunction:
    """Define and evaluate architecture fitness functions."""

    def __init__(self):
        self._functions: List[Dict] = []

    def define(self, name: str, description: str, metric: str, threshold: float):
        self._functions.append({
            "name": name, "description": description,
            "metric": metric, "threshold": threshold,
            "current_value": None, "passing": None,
        })

    def evaluate(self, name: str, value: float) -> bool:
        for fn in self._functions:
            if fn["name"] == name:
                fn["current_value"] = value
                fn["passing"] = value >= fn["threshold"] if fn["metric"] != "latency" else value <= fn["threshold"]
                return fn["passing"]
        return False

    def get_report(self) -> Dict:
        passing = sum(1 for f in self._functions if f["passing"])
        return {
            "total": len(self._functions),
            "passing": passing,
            "failing": len(self._functions) - passing,
            "details": self._functions,
        }
