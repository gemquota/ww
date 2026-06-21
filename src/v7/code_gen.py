"""V7-16: Code Generation quality — readability, patterns, boilerplate (Alex Kim)."""
from typing import Dict, List, Optional
import ast


class CodeReadability:
    """Analyze generated code readability."""

    @staticmethod
    def score_readability(code: str) -> Dict:
        """Score code readability on multiple dimensions."""
        lines = code.split("\n")
        total_lines = len(lines)
        if total_lines == 0 or not any(l.strip() for l in lines):
            return {"score": 0, "issues": ["Empty code"]}

        issues = []
        avg_line_length = sum(len(l) for l in lines if l.strip()) / max(sum(1 for l in lines if l.strip()), 1)
        if avg_line_length > 80:
            issues.append(f"Average line length {avg_line_length:.0f} > 80")

        comment_ratio = sum(1 for l in lines if l.strip().startswith("#")) / max(total_lines, 1)
        if comment_ratio < 0.05 and total_lines > 20:
            issues.append("Low comment ratio (<5%)")

        has_docstring = '"""' in code or "'''" in code
        if not has_docstring and total_lines > 10:
            issues.append("No docstring found")

        # Score: 100 - 20 per issue
        score = max(0, 100 - len(issues) * 20)
        return {"score": score, "issues": issues, "avg_line_length": round(avg_line_length, 1)}

    @staticmethod
    def check_pattern_consistency(code: str) -> List[Dict]:
        """Check for inconsistent patterns in generated code."""
        issues = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [{"type": "syntax_error", "detail": "Cannot parse code"}]

        funcs = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        styles = set()
        for func in funcs:
            for node in ast.walk(func):
                if isinstance(node, ast.Return):
                    styles.add("return")
                elif isinstance(node, ast.Yield):
                    styles.add("generator")

        if "return" in styles and "generator" in styles:
            issues.append({"type": "inconsistent_pattern", "detail": "Mix of return and yield in same scope"})

        return issues


class BoilerplateReducer:
    """Identify and reduce boilerplate in generated code."""

    COMMON_PATTERNS = [
        ("try/except/pass", "try:\n    ...\nexcept:\n    pass"),
        ("empty __init__", "def __init__(self):\n    pass"),
    ]

    @staticmethod
    def find_boilerplate(code: str) -> List[Dict]:
        """Find boilerplate patterns in code."""
        found = []
        if "except:\n    pass" in code:
            found.append({"type": "bare_except", "suggestion": "Specify exception type instead of bare except"})
        if "def __init__(self):\n    pass" in code:
            found.append({"type": "empty_init", "suggestion": "Remove unnecessary empty __init__"})
        return found


class TemplateEfficiency:
    """Analyze template rendering efficiency."""

    @staticmethod
    def analyze_template(template: str) -> Dict:
        """Analyze a template for efficiency improvements."""
        slot_count = template.count("{{") if "{{" in template else template.count("{")
        static_ratio = 1.0 - (slot_count / max(len(template), 1))
        return {
            "template_length": len(template),
            "slot_count": slot_count,
            "static_content_ratio": round(static_ratio, 3),
            "efficiency_score": round(min(1.0, static_ratio * 2), 2),
        }
