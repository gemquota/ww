"""Small, dependency-free parser for WW's explicit textual tool protocol."""

import re


def extract_tool_blocks(response_text: str) -> list[tuple[str, str]]:
    """Extract top-level WW tool fences, ignoring ordinary Markdown examples.

    A normal Markdown fence is opaque. Only an info string beginning with
    tool:<name> is executable. Closing fences must match the opening marker.
    """
    blocks: list[tuple[str, str]] = []
    fence_char: str | None = None
    fence_length = 0
    active_tool: str | None = None
    body: list[str] = []

    for line in (response_text or "").splitlines():
        opener = re.match(r"^ {0,3}(\x60{3,}|~{3,})(.*)$", line)
        if fence_char is None:
            if not opener:
                continue
            marker, info = opener.groups()
            fence_char = marker[0]
            fence_length = len(marker)
            tool_match = re.fullmatch(r"tool:(\w+)(?:\s+.*)?", info.strip())
            active_tool = tool_match.group(1) if tool_match else None
            body = []
            continue

        closer = re.match(r"^ {0,3}(\x60+|~+)\s*$", line)
        if (
            closer
            and closer.group(1)[0] == fence_char
            and len(closer.group(1)) >= fence_length
        ):
            if active_tool:
                blocks.append((active_tool, "\n".join(body).strip("\n")))
            fence_char = None
            fence_length = 0
            active_tool = None
            body = []
        elif active_tool:
            body.append(line)

    # An unclosed fence is deliberately ignored: partial output is not executable.
    return blocks
