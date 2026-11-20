"""Syntax-check the inline JavaScript in the static browser workspace."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    html_path = Path(__file__).resolve().parent.parent / "src" / "dashboard" / "chat.html"
    html = html_path.read_text(encoding="utf-8")
    scripts = [
        body for body in re.findall(
            r"<script(?:\s[^>]*)?>(.*?)</script>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if body.strip()
    ]
    if not scripts:
        raise SystemExit("No inline JavaScript found in src/dashboard/chat.html")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as handle:
        handle.write("\n;\n".join(scripts))
        handle.flush()
        result = subprocess.run(["node", "--check", handle.name], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    print(f"JavaScript syntax valid ({len(scripts)} inline script block(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
