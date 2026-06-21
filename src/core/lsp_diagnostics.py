"""LSP-style diagnostics for code quality analysis."""
import ast
import re
from pathlib import Path
from typing import List, Dict, Optional


class Diagnostic:
    """A single diagnostic issue found in source code."""
    
    def __init__(self, file_path: str, line: int, message: str, severity: str = "warning",
                 code: str = "", suggestion: str = ""):
        self.file_path = file_path
        self.line = line
        self.message = message
        self.severity = severity  # "error", "warning", "info", "hint"
        self.code = code
        self.suggestion = suggestion

    def __repr__(self):
        return f"[{self.severity.upper()}] {self.file_path}:{self.line} — {self.message}"


class LSPDiagnostics:
    """Provides LSP-style diagnostics for the codebase."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def check_all(self) -> List[Diagnostic]:
        """Run all diagnostic checks."""
        diagnostics = []
        diagnostics.extend(self._check_import_errors())
        diagnostics.extend(self._check_print_statements())
        diagnostics.extend(self._check_todo_comments())
        diagnostics.extend(self._check_deprecated_patterns())
        return diagnostics

    def _check_import_errors(self) -> List[Diagnostic]:
        """Find files with syntax or import errors."""
        issues = []
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            try:
                ast.parse(pyfile.read_text())
            except SyntaxError as e:
                issues.append(Diagnostic(rel, e.lineno or 0, f"Syntax error: {e}", "error"))
        return issues

    def _check_print_statements(self) -> List[Diagnostic]:
        """Find print() calls that should be logging instead."""
        issues = []
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            if pyfile.name == "__init__.py":
                continue
            rel = str(pyfile.relative_to(self.root))
            text = pyfile.read_text()
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                    issues.append(Diagnostic(
                        rel, node.lineno,
                        "Use logger instead of print()",
                        "warning", "P001",
                        "Replace with logger.info() or logging.debug()"
                    ))
        return issues

    def _check_todo_comments(self) -> List[Diagnostic]:
        """Find TODO/FIXME/HACK comments."""
        issues = []
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            text = pyfile.read_text()
            for i, line in enumerate(text.split('\n'), 1):
                if 'TODO' in line or 'FIXME' in line or 'HACK' in line or 'XXX' in line:
                    msg = line.strip()[:80]
                    issues.append(Diagnostic(rel, i, f"TODO/FIXME: {msg}", "info", "P002"))
        return issues

    def _check_deprecated_patterns(self) -> List[Diagnostic]:
        """Check for deprecated API usage patterns."""
        issues = []
        deprecated = {
            r"\.get_bus\(": "get_bus() is deprecated — use BridgeContext directly",
            r"\.reset_bus\(": "reset_bus() is deprecated — use BridgeContext directly",
            r"load_dotenv\(\)": "load_dotenv() should be called once at entry point, not in modules",
        }
        for pyfile in sorted(self.root.rglob("src/**/*.py")):
            rel = str(pyfile.relative_to(self.root))
            text = pyfile.read_text()
            for pattern, message in deprecated.items():
                for match in re.finditer(pattern, text):
                    line_num = text[:match.start()].count('\n') + 1
                    issues.append(Diagnostic(rel, line_num, message, "warning", "P003"))
        return issues

    def get_file_diagnostics(self, file_path: str) -> List[Diagnostic]:
        """Get diagnostics for a single file."""
        return [d for d in self.check_all() if d.file_path == file_path]

    def summary(self) -> Dict[str, int]:
        """Get count of diagnostics by severity."""
        all_diags = self.check_all()
        return {
            "error": sum(1 for d in all_diags if d.severity == "error"),
            "warning": sum(1 for d in all_diags if d.severity == "warning"),
            "info": sum(1 for d in all_diags if d.severity == "info"),
            "total": len(all_diags),
        }
