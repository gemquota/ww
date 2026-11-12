"""Project inventory and source-context exporter used by WW's /context command.

The exporter is deliberately stdlib-only. It inventories the complete visible
project tree, embeds ordinary text files, samples large text files, and omits
sensitive contents and binary payloads by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_IGNORES = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "node_modules", "bower_components",
    "dist", "build", ".next", ".nuxt", ".svelte-kit", ".turbo", "coverage",
    ".idea", ".vscode", ".gradle", ".terraform", "target", ".ww",
}
SENSITIVE_NAMES = {
    ".env", ".env.local", ".env.production", "cookies.txt", "cookie.txt",
    "id_rsa", "id_ed25519", "credentials.json", "secrets.json",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json",
    ".jsonc", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    ".cmd", ".html", ".htm", ".css", ".scss", ".sass", ".less", ".xml",
    ".svg", ".sql", ".graphql", ".gql", ".proto", ".go", ".rs", ".c", ".h",
    ".cpp", ".hpp", ".java", ".kt", ".kts", ".swift", ".rb", ".php", ".pl",
    ".lua", ".r", ".jl", ".ex", ".exs", ".erl", ".hrl", ".hs", ".lhs",
    ".dart", ".vue", ".svelte", ".astro", ".ipynb", ".tf", ".dockerfile",
    ".make", ".mk", ".gradle", ".properties", ".gitignore", ".gitattributes",
    ".editorconfig", ".prettierrc", ".eslintrc",
}
ROOT_MARKERS = (
    ".git", "pyproject.toml", "setup.py", "setup.cfg", "package.json",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "Makefile",
)


def find_project_root(cwd: Path, explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Project root is not a directory: {root}")
        return root
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.TimeoutExpired):
        pass
    for candidate in (cwd, *cwd.parents):
        if any((candidate / marker).exists() for marker in ROOT_MARKERS):
            return candidate
    return cwd


def _text_file(path: Path, size: int, full_limit: int, sample_bytes: int) -> dict[str, Any]:
    with path.open("rb") as stream:
        prefix = stream.read(min(size, 8192))
        if b"\x00" in prefix:
            return {"kind": "binary", "content": None, "sampled": False}
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            try:
                prefix.decode("utf-8")
            except UnicodeDecodeError:
                return {"kind": "binary", "content": None, "sampled": False}
        if size <= full_limit:
            stream.seek(0)
            data = stream.read(full_limit + 1)
            return {
                "kind": "text",
                "content": data.decode("utf-8", errors="replace"),
                "sampled": False,
            }
        stream.seek(0)
        head = stream.read(sample_bytes)
        stream.seek(max(0, size - sample_bytes))
        tail = stream.read(sample_bytes)
        return {
            "kind": "text",
            "content": (
                head.decode("utf-8", errors="replace")
                + "\n\n[... CONTENT SAMPLED: middle omitted ...]\n\n"
                + tail.decode("utf-8", errors="replace")
            ),
            "sampled": True,
            "sampling": {
                "strategy": "first_and_last_bytes",
                "head_bytes": len(head),
                "tail_bytes": len(tail),
                "omitted_bytes": max(0, size - len(head) - len(tail)),
            },
        }


def export_project(
    root: Path,
    cwd: Path,
    output: Path,
    *,
    full_limit: int = 256 * 1024,
    sample_bytes: int = 32 * 1024,
    hash_limit: int = 64 * 1024 * 1024,
    max_content_bytes: int = 12 * 1024 * 1024,
    ignores: set[str] | None = None,
    include_sensitive: bool = False,
) -> dict[str, Any]:
    ignored = DEFAULT_IGNORES | (ignores or set())
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    output_resolved = output.resolve()
    content_used = 0

    for current, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in ignored and not (base / name).is_symlink()
        )
        relative_dir = base.relative_to(root)
        if relative_dir != Path("."):
            entries.append({"type": "directory", "path": relative_dir.as_posix()})

        for filename in sorted(filenames):
            path = base / filename
            try:
                if path.resolve() == output_resolved:
                    continue
                relative = path.relative_to(root).as_posix()
                if path.is_symlink():
                    entries.append({
                        "type": "symlink", "path": relative, "target": os.readlink(path),
                    })
                    continue
                stat = path.stat()
                suffix = path.suffix.lower()
                record: dict[str, Any] = {
                    "type": "file",
                    "path": relative,
                    "name": filename,
                    "extension": suffix,
                    "size_bytes": stat.st_size,
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "mime_type": mimetypes.guess_type(filename)[0],
                    "sha256": None,
                }
                lower_name = filename.lower()
                sensitive = lower_name != ".env.example" and (
                    lower_name in SENSITIVE_NAMES
                    or suffix in SENSITIVE_SUFFIXES
                    or lower_name.startswith(".env.")
                    or ("cookie" in lower_name and suffix in {".txt", ".json"})
                )
                if sensitive and not include_sensitive:
                    record.update({
                        "kind": "sensitive", "content": None,
                        "content_omitted": "sensitive_file",
                    })
                else:
                    try:
                        data = _text_file(path, stat.st_size, full_limit, sample_bytes)
                        content_size = len(str(data.get("content") or "").encode("utf-8"))
                        if content_size and content_used + content_size > max_content_bytes:
                            data = {
                                "kind": data.get("kind", "text"),
                                "content": None,
                                "sampled": data.get("sampled", False),
                                "content_omitted": "export_content_budget",
                            }
                        else:
                            content_used += content_size
                        record.update(data)
                    except (OSError, UnicodeError) as exc:
                        record.update({
                            "kind": "unreadable", "content": None,
                            "read_error": f"{type(exc).__name__}: {exc}",
                        })
                if stat.st_size <= hash_limit and not sensitive:
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    record["sha256"] = digest.hexdigest()
                entries.append(record)
            except OSError as exc:
                skipped.append({
                    "path": str(path), "error": f"{type(exc).__name__}: {exc}",
                })

    entries.sort(key=lambda item: (item["path"].casefold(), item["type"]))
    return {
        "format": "ww-project-context",
        "format_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "working_directory": str(cwd),
        "project_root": str(root),
        "output_file": str(output),
        "settings": {
            "full_file_limit_bytes": full_limit,
            "large_file_sample_bytes_per_end": sample_bytes,
            "hash_limit_bytes": hash_limit,
            "max_content_bytes": max_content_bytes,
            "ignored_directory_names": sorted(ignored),
            "sensitive_file_contents_included": include_sensitive,
        },
        "summary": {
            "entries": len(entries),
            "files": sum(item["type"] == "file" for item in entries),
            "directories": sum(item["type"] == "directory" for item in entries),
            "symlinks": sum(item["type"] == "symlink" for item in entries),
            "sampled_files": sum(item.get("sampled", False) for item in entries),
            "binary_files": sum(item.get("kind") == "binary" for item in entries),
            "sensitive_files_omitted": sum(item.get("kind") == "sensitive" for item in entries),
            "content_omitted": sum("content_omitted" in item for item in entries),
            "read_errors": len(skipped) + sum(item.get("kind") == "unreadable" for item in entries),
            "content_bytes": content_used,
        },
        "entries": entries,
        "skipped": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export a project inventory and text context as JSON.")
    parser.add_argument("--root", help="Project root; defaults to detected Git/project root.")
    parser.add_argument("--output", help="Output JSON path; defaults to .ww/project-context.json.")
    parser.add_argument("--full-limit", type=int, default=256 * 1024)
    parser.add_argument("--sample-bytes", type=int, default=32 * 1024)
    parser.add_argument("--hash-limit", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-content-bytes", type=int, default=12 * 1024 * 1024)
    parser.add_argument("--ignore", action="append", default=[])
    args = parser.parse_args(argv)
    if min(args.full_limit, args.sample_bytes, args.hash_limit, args.max_content_bytes) < 0:
        parser.error("Size limits must be zero or greater.")
    cwd = Path.cwd().resolve()
    root = find_project_root(cwd, args.root)
    output = Path(args.output).expanduser() if args.output else root / ".ww" / "project-context.json"
    if not output.is_absolute():
        output = (cwd / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = export_project(
        root, cwd, output,
        full_limit=args.full_limit,
        sample_bytes=args.sample_bytes,
        hash_limit=args.hash_limit,
        max_content_bytes=args.max_content_bytes,
        ignores=set(args.ignore),
    )
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **document["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
