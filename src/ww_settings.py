"""Persistent, local-only preferences and chat folder metadata for WW."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def settings_path() -> Path:
    root = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "ww" / "settings.json"


def load_settings() -> dict[str, Any]:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("chat_page_size", 15)
    data.setdefault("default_model", None)
    data.setdefault("default_gem", None)
    data.setdefault("chat_folders", {})
    data.setdefault("context_root", None)
    data.setdefault("context_output", None)
    data.setdefault("context_ignores", [])
    data.setdefault("context_includes", [])
    return data


def save_settings(settings: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="settings-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def normalize_folder(name: str) -> str:
    return " ".join(name.strip().split())


def assign_chat_folder(settings: dict[str, Any], chat_id: str, folder: str | None) -> None:
    folders = settings.setdefault("chat_folders", {})
    if folder is None:
        folders.pop(chat_id, None)
        return
    normalized = normalize_folder(folder)
    if not normalized:
        raise ValueError("Folder name must not be empty.")
    folders[chat_id] = normalized


def folder_names(settings: dict[str, Any]) -> list[str]:
    """Return unique folder labels, deduplicated without regard to case or spacing."""
    unique: dict[str, str] = {}
    for value in settings.get("chat_folders", {}).values():
        normalized = normalize_folder(str(value))
        if normalized:
            unique.setdefault(normalized.casefold(), normalized)
    return sorted(unique.values(), key=str.casefold)


def chats_in_folder(chats: list[Any], settings: dict[str, Any], folder: str) -> list[Any]:
    mapping = settings.get("chat_folders", {})
    target = normalize_folder(folder).casefold()
    return [chat for chat in chats if str(mapping.get(chat.cid, "")).casefold() == target]
