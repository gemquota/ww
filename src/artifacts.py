"""Local multimodal artifact storage and structured Gemini response rendering."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.markdown_renderer import render_response


def artifact_root() -> Path:
    """Return WW's XDG-compliant artifact directory."""
    data_home = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "ww" / "artifacts"


def _safe_segment(value: str | None, fallback: str = "unassigned") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-.")
    return value[:80] or fallback


def conversation_artifact_dir(chat_id: str | None) -> Path:
    return artifact_root() / _safe_segment(chat_id)


def preview_image(path: Path) -> bool:
    """Render an image in capable terminals; leave opening to the user otherwise."""
    if shutil.which("chafa"):
        command = ["chafa", "--size=60x25", str(path)]
    elif shutil.which("viu"):
        command = ["viu", "-w", "60", str(path)]
    else:
        return False
    try:
        subprocess.run(command, check=False)
        return True
    except OSError:
        return False


def save_research_document(document: Any, chat_id: str | None = None) -> Path | None:
    """Persist a finished Deep Research report as a self-contained Markdown file."""
    content = getattr(document, "markdown", None)
    if not content:
        content = getattr(document, "content", "")
    if not str(content).strip():
        return None
    title = getattr(document, "title", None) or "research-report"
    filename = _safe_segment(title, "research-report") + ".md"
    directory = conversation_artifact_dir(chat_id) / "research"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    if destination.exists():
        stem, suffix, index = destination.stem, destination.suffix, 2
        while destination.exists():
            destination = directory / f"{stem}-{index}{suffix}"
            index += 1
    destination.write_text(str(content), encoding="utf-8")
    return destination


async def save_model_artifacts(
    output: Any,
    chat_id: str | None = None,
    media_mode: str = "auto",
) -> list[Path]:
    """Download all classified media attached to a ModelOutput.

    This intentionally uses the media objects' own save methods so authentication,
    generated-image full-size retrieval, and video render polling stay upstream-owned.
    """
    saved: list[Path] = []
    root = conversation_artifact_dir(chat_id)

    document = getattr(output, "deep_research_document", None)
    if document is not None and getattr(document, "ready", bool(getattr(document, "content", ""))):
        path = save_research_document(document, chat_id)
        if path:
            saved.append(path)

    images = list(getattr(output, "images", ()) or ())
    if images:
        directory = root / "images"
        directory.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(images, 1):
            try:
                path = await item.save(path=str(directory), filename=f"image-{index:02}.png")
                if path:
                    image_path = Path(path)
                    saved.append(image_path)
                    preview_image(image_path)
            except Exception as exc:
                print(f"Could not save image {index}: {exc}")

    videos = list(getattr(output, "videos", ()) or ())
    if videos:
        directory = root / "videos"
        directory.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(videos, 1):
            try:
                result = await item.save(
                    path=str(directory), filename=f"video-{index:02}.mp4"
                )
                for value in (result or {}).values():
                    if value and value != "206":
                        saved.append(Path(value))
            except Exception as exc:
                print(f"Could not save video {index}: {exc}")

    media = list(getattr(output, "media", ()) or ())
    if media:
        directory = root / "audio"
        directory.mkdir(parents=True, exist_ok=True)
        for index, item in enumerate(media, 1):
            try:
                download_type = "audio" if media_mode in {"audio", "music"} else "both"
                result = await item.save(
                    path=str(directory),
                    filename=f"audio-{index:02}.mp3",
                    download_type=download_type,
                )
                for key, value in (result or {}).items():
                    if value and value != "206" and (download_type == "both" or key.startswith("audio")):
                        saved.append(Path(value))
            except Exception as exc:
                print(f"Could not save generated audio {index}: {exc}")

    return saved


async def render_model_output(
    output: Any,
    chat_id: str | None = None,
    media_mode: str = "auto",
) -> tuple[Any, list[Path]]:
    """Render text and attached research/media, then persist downloadable artifacts."""
    response_text = getattr(output, "text", None)
    if response_text:
        options = render_response(response_text)
    else:
        options = ()

    document = getattr(output, "deep_research_document", None)
    if document is not None and getattr(document, "ready", bool(getattr(document, "content", ""))):
        markdown = getattr(document, "markdown", None) or getattr(document, "content", "")
        title = getattr(document, "title", None) or "Deep Research report"
        print(f"\nDeep Research report: {title}")
        render_response(markdown)

    for index, item in enumerate(getattr(output, "images", ()) or (), 1):
        title = getattr(item, "title", None) or f"Image {index}"
        alt = getattr(item, "alt", None)
        print(f"\n{title}" + (f": {alt}" if alt else ""))
    for index, item in enumerate(getattr(output, "videos", ()) or (), 1):
        print(f"\nGenerated video {index}: {getattr(item, 'title', None) or 'Untitled'}")
    for index, item in enumerate(getattr(output, "media", ()) or (), 1):
        print(f"\nGenerated audio {index}: {getattr(item, 'title', None) or 'Untitled'}")

    saved = await save_model_artifacts(output, chat_id, media_mode=media_mode)
    if saved:
        print("\nSaved artifacts:")
        for path in saved:
            print(f"  {path}")
        print("Use /artifacts to browse them and /open N to open one.")
    return options, saved


def list_artifacts() -> list[Path]:
    """List saved artifacts, newest first."""
    root = artifact_root()
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
