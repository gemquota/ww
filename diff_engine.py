"""
Fuzzy SEARCH/REPLACE Engine with Colorized Diff Display.

Frontier-grade file editing inspired by Aider's edit formats.
Implements fault-tolerant fuzzy matching so that minor whitespace
or indentation differences from the LLM don't cause edit failures.
"""

import difflib
import re
from pathlib import Path
from typing import Optional, Tuple, List
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


class DiffEngine:
    """Handles fuzzy file editing and diff display."""

    # Minimum similarity ratio for fuzzy matching (0.0 to 1.0)
    FUZZY_THRESHOLD = 0.85

    @staticmethod
    def fuzzy_find(content: str, search_block: str) -> Optional[Tuple[int, int]]:
        """
        Find the best fuzzy match for search_block within content.

        Returns (start_index, end_index) of the best match, or None if
        no match exceeds the similarity threshold.
        """
        if not search_block.strip():
            return None

        # First, try exact match
        idx = content.find(search_block)
        if idx != -1:
            return (idx, idx + len(search_block))

        # Try with normalized whitespace (strip trailing spaces per line)
        search_lines = search_block.splitlines()
        content_lines = content.splitlines()

        search_stripped = [line.rstrip() for line in search_lines]
        content_stripped = [line.rstrip() for line in content_lines]

        # Try exact match with stripped lines
        search_joined = "\n".join(search_stripped)
        content_joined_stripped = "\n".join(content_stripped)
        idx = content_joined_stripped.find(search_joined)
        if idx != -1:
            # Map back to original content positions
            line_start = content_joined_stripped[:idx].count("\n")
            line_end = line_start + len(search_lines)
            original_start = sum(len(content_lines[i]) + 1 for i in range(line_start))
            original_end = sum(len(content_lines[i]) + 1 for i in range(line_end)) - 1
            return (original_start, original_end)

        # Fuzzy matching using SequenceMatcher on lines
        best_ratio = 0.0
        best_start = -1
        best_end = -1
        search_len = len(search_lines)

        for i in range(len(content_lines) - search_len + 1):
            candidate = content_lines[i:i + search_len]
            candidate_stripped = [line.rstrip() for line in candidate]

            matcher = difflib.SequenceMatcher(
                None,
                search_stripped,
                candidate_stripped,
            )
            ratio = matcher.ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i
                best_end = i + search_len

        if best_ratio >= DiffEngine.FUZZY_THRESHOLD:
            # Calculate character positions from line positions
            start_pos = sum(len(content_lines[i]) + 1 for i in range(best_start))
            end_pos = sum(len(content_lines[i]) + 1 for i in range(best_end)) - 1
            return (start_pos, end_pos)

        return None

    @staticmethod
    def apply_edit(
        filepath: Path,
        search_block: str,
        replace_block: str,
    ) -> Tuple[bool, str, str]:
        """
        Apply a SEARCH/REPLACE edit to a file with fuzzy matching.

        Returns:
            (success, message, colorized_diff)
        """
        if not filepath.exists():
            return False, f"File not found: {filepath}", ""

        content = filepath.read_text(encoding="utf-8", errors="ignore")
        original_content = content

        match = DiffEngine.fuzzy_find(content, search_block)
        if match is None:
            # Try one more strategy: ignore all leading whitespace
            dedented_search = "\n".join(
                line.lstrip() for line in search_block.splitlines()
            )
            dedented_content = "\n".join(
                line.lstrip() for line in content.splitlines()
            )
            idx = dedented_content.find(dedented_search)
            if idx == -1:
                return (
                    False,
                    f"Could not find matching text in {filepath.name} "
                    f"(even with fuzzy matching at {DiffEngine.FUZZY_THRESHOLD:.0%} threshold).",
                    "",
                )
            # If dedented match works, use line-based replacement
            content_lines = content.splitlines(keepends=True)
            search_lines = search_block.splitlines()
            dedented_content_lines = [l.lstrip() for l in content.splitlines()]

            # Find the starting line
            target = dedented_search.splitlines()[0]
            for i, line in enumerate(dedented_content_lines):
                if line.startswith(target):
                    # Check if subsequent lines match
                    candidate = dedented_content_lines[i:i + len(search_lines)]
                    if "\n".join(candidate) == dedented_search:
                        match = (
                            sum(len(content_lines[j]) for j in range(i)),
                            sum(len(content_lines[j]) for j in range(i + len(search_lines))),
                        )
                        break

            if match is None:
                return (
                    False,
                    f"Could not reliably locate text in {filepath.name}.",
                    "",
                )

        start, end = match
        new_content = content[:start] + replace_block + content[end:]

        # Write the new content
        filepath.write_text(new_content, encoding="utf-8")

        # Generate colorized diff
        diff_output = DiffEngine.colorize_diff(
            original_content, new_content, str(filepath)
        )

        return True, f"Successfully edited {filepath.name}", diff_output

    @staticmethod
    def colorize_diff(old_content: str, new_content: str, filename: str) -> str:
        """Generate a colorized unified diff string."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )

        output_lines = []
        for line in diff:
            line = line.rstrip("\n")
            if line.startswith("+++") or line.startswith("---"):
                output_lines.append(f"{Fore.WHITE}{Style.BRIGHT}{line}{Style.RESET_ALL}")
            elif line.startswith("@@"):
                output_lines.append(f"{Fore.CYAN}{line}{Style.RESET_ALL}")
            elif line.startswith("+"):
                output_lines.append(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
            elif line.startswith("-"):
                output_lines.append(f"{Fore.RED}{line}{Style.RESET_ALL}")
            else:
                output_lines.append(line)

        return "\n".join(output_lines)

    @staticmethod
    def show_file_diff(filepath: Path, old_content: str) -> str:
        """Show diff between old content and current file content."""
        if not filepath.exists():
            return ""
        new_content = filepath.read_text(encoding="utf-8", errors="ignore")
        return DiffEngine.colorize_diff(old_content, new_content, str(filepath))
