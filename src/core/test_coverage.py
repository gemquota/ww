"""Test coverage analysis and culture tooling."""
import ast
from pathlib import Path
from typing import List, Tuple, Set


class CoverageAnalyzer:
    """Analyzes test coverage gaps across the codebase."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def find_untested_modules(self) -> List[Tuple[str, str]]:
        """Find source modules without corresponding test files."""
        src_files = set()
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            if pyfile.name == "__init__.py":
                continue
            rel = str(pyfile.relative_to(self.root))
            src_files.add(rel)

        test_files = set()
        for pyfile in sorted(self.root.rglob(".tel/tests/**/*.py")):
            if pyfile.name in ("__init__.py", "conftest.py"):
                continue
            test_files.add(pyfile.stem.replace("test_", ""))

        uncovered = []
        for src in src_files:
            module_name = Path(src).stem
            if module_name not in test_files and module_name != "__init__":
                uncovered.append((src, "no test file"))
        return uncovered

    def function_coverage(self, module_path: str) -> dict:
        """Analyze what functions in a module are tested."""
        src_path = self.root / module_path
        if not src_path.exists():
            return {"error": "File not found"}

        src_tree = ast.parse(src_path.read_text())
        functions = []
        for node in ast.walk(src_tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)

        return {
            "module": module_path,
            "total_functions": len(functions),
            "functions": functions,
        }


class DocumentationEffectiveness:
    """Evaluates documentation quality metrics."""

    @staticmethod
    def check_prerequisites(doc_path: str) -> List[str]:
        """Check if a doc has prerequisites listed."""
        text = Path(doc_path).read_text()
        missing = []
        for section in ["prerequisite", "before you begin", "requirements", "install"]:
            if section not in text.lower():
                missing.append(section)
        return missing

    @staticmethod
    def check_code_examples(doc_path: str) -> int:
        """Count code examples in a document."""
        import re
        text = Path(doc_path).read_text()
        return len(re.findall(r'```', text)) // 2

    @staticmethod
    def check_troubleshooting(doc_path: str) -> bool:
        """Check if doc has troubleshooting section."""
        text = Path(doc_path).read_text().lower()
        return "troubleshooting" in text or "common issues" in text or "faq" in text
