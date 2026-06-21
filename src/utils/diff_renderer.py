"""Side-by-side diff rendering — NEW-V5-E2#2 (Ingrid Larsen).
Terminal-based side-by-side diff viewer for SEARCH/REPLACE changes.
"""
import difflib
from typing import List, Tuple, Optional


def _format_line(line: str, width: int = 50) -> str:
    """Truncate or pad a line to fixed width for side-by-side display."""
    line = line.rstrip('\n').expandtabs(2)
    if len(line) > width:
        line = line[:width - 3] + "..."
    return line.ljust(width)


def render_side_by_side(
    original: str,
    modified: str,
    context_lines: int = 3,
    line_numbers: bool = True
) -> str:
    """Render a side-by-side diff of two strings.
    
    Args:
        original: Original file content
        modified: Modified file content
        context_lines: Lines of context around changes
        line_numbers: Show line numbers
        
    Returns:
        Formatted side-by-side diff string
    """
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    
    differ = difflib.SequenceMatcher(None, orig_lines, mod_lines)
    result: List[str] = []
    
    # Header
    result.append(f"{'─' * 52}  {'─' * 52}")
    result.append(f"{'  ORIGINAL':50}    {'  MODIFIED':50}")
    result.append(f"{'─' * 52}  {'─' * 52}")
    
    for op, i1, i2, j1, j2 in differ.get_opcodes():
        if op == 'equal':
            # Show context lines around changes
            if i2 - i1 > context_lines * 2:
                # Show first N, skip middle, show last N
                for idx in range(i1, i1 + context_lines):
                    _append_line(result, orig_lines[idx], mod_lines[idx] if idx - i1 + j1 < j2 else "", line_numbers, idx + 1)
                result.append(f"{'  ...':50}    {'  ...':50}")
                for idx in range(i2 - context_lines, i2):
                    _append_line(result, orig_lines[idx], mod_lines[idx] if idx - i1 + j1 < j2 else "", line_numbers, idx + 1)
            else:
                for idx in range(i1, i2):
                    _append_line(result, orig_lines[idx], orig_lines[idx], line_numbers, idx + 1)
        elif op == 'replace':
            # Show replaced lines side by side
            for idx in range(max(i2 - i1, j2 - j1)):
                orig_line = orig_lines[i1 + idx] if i1 + idx < i2 else ""
                mod_line = mod_lines[j1 + idx] if j1 + idx < j2 else ""
                _append_line(result, orig_line, mod_line, line_numbers, i1 + idx + 1, j1 + idx + 1, changed=True)
        elif op == 'delete':
            for idx in range(i1, i2):
                _append_line(result, orig_lines[idx], "", line_numbers, idx + 1, changed=True)
        elif op == 'insert':
            for idx in range(j1, j2):
                _append_line(result, "", mod_lines[idx], line_numbers, idx + 1, changed=True)
    
    result.append(f"{'─' * 52}  {'─' * 52}")
    return '\n'.join(result)


def _append_line(
    result: List[str],
    orig_line: str,
    mod_line: str,
    line_numbers: bool,
    orig_lineno: int = 0,
    mod_lineno: int = 0,
    changed: bool = False,
    width: int = 50
):
    """Append a formatted side-by-side line pair."""
    marker = "▎" if changed else " "
    o = _format_line(orig_line, width)
    m = _format_line(mod_line, width)
    if line_numbers:
        o_num = f"{orig_lineno:>4}" if orig_lineno else "    "
        m_num = f"{mod_lineno:>4}" if mod_lineno else "    "
        result.append(f"{marker}{o_num} {o}  {marker}{m_num} {m}")
    else:
        result.append(f"{marker} {o}  {marker} {m}")


class DiffPreview:
    """Preview changes with side-by-side rendering and file-level summary."""

    @staticmethod
    def preview_file_changes(file_path: str, original: str, modified: str) -> str:
        """Generate a preview of changes for a single file."""
        if original == modified:
            return f"  ✓ {file_path} — no changes"
        
        orig_lines = original.count('\n')
        mod_lines = modified.count('\n')
        added = sum(1 for a, b in zip(original.splitlines(), modified.splitlines()) if a != b)
        
        header = (
            f"  File: {file_path}\n"
            f"  Lines: {orig_lines} → {mod_lines} "
            f"({'+' if mod_lines >= orig_lines else ''}{mod_lines - orig_lines})\n"
        )
        return header + '\n' + render_side_by_side(original, modified)

    @staticmethod
    def batch_preview(changes: List[Tuple[str, str, str]]) -> str:
        """Preview multiple file changes."""
        sections = []
        for file_path, original, modified in changes:
            sections.append(DiffPreview.preview_file_changes(file_path, original, modified))
        return '\n\n'.join(sections)
