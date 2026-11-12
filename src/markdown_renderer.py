"""Markdown rendering and Gemini elicitation parsing for the WW terminal."""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TextIO

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text


@dataclass(frozen=True)
class Elicitation:
    """A selectable Gemini follow-up action."""

    label: str
    query: str


@dataclass(frozen=True)
class ElicitationGroup:
    """A group of selectable follow-up actions."""

    message: str
    options: tuple[Elicitation, ...]


@dataclass(frozen=True)
class ParsedResponse:
    """Markdown body plus any interactive follow-up groups."""

    markdown: str
    groups: tuple[ElicitationGroup, ...]

    @property
    def options(self) -> tuple[Elicitation, ...]:
        return tuple(option for group in self.groups for option in group.options)


class _AttributeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.attributes: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attributes = dict(attrs)


class _ElicitationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.options: list[Elicitation] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._add(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._add(tag, attrs)

    def _add(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "elicitation":
            return
        values = dict(attrs)
        label = values.get("label")
        query = values.get("query")
        if label and query:
            self.options.append(Elicitation(label=label.strip(), query=query.strip()))


_GROUP_RE = re.compile(
    r"<ElicitationsGroup\b(?P<attrs>[^>]*)>(?P<body>.*?)</ElicitationsGroup\s*>",
    re.IGNORECASE | re.DOTALL,
)
_FENCED_CODE_RE = re.compile(r"(^|\n)( {0,3})(`{3,}|~{3,})[^\n]*\n.*?\n\2\3[ 	]*(?=\n|$)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)


def _protect_code(source: str) -> tuple[str, list[str]]:
    """Hide code spans while parsing component-like text."""
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        token = f"WWCODEBLOCK{len(protected)}TOKEN"
        protected.append(match.group(0))
        return token

    source = _FENCED_CODE_RE.sub(stash, source)
    source = _INLINE_CODE_RE.sub(stash, source)
    return source, protected


def _restore_code(source: str, protected: list[str]) -> str:
    for index, value in enumerate(protected):
        source = source.replace(f"WWCODEBLOCK{index}TOKEN", value)
    return source


def parse_response(source: str) -> ParsedResponse:
    """Extract Gemini ElicitationsGroup components without touching code examples.

    Invalid or incomplete component markup is retained as ordinary Markdown so
    the renderer never silently destroys a model response.
    """
    protected_source, protected = _protect_code(source)
    groups: list[ElicitationGroup] = []

    def replace_group(match: re.Match[str]) -> str:
        attrs = _AttributeParser()
        attrs.feed(f"<group {match.group('attrs')}>")
        message = (attrs.attributes.get("message") or "").strip()

        parser = _ElicitationParser()
        parser.feed(match.group("body"))
        if not parser.options:
            return match.group(0)

        groups.append(ElicitationGroup(message=message, options=tuple(parser.options)))
        return ""

    markdown = _GROUP_RE.sub(replace_group, protected_source)
    markdown = _restore_code(markdown, protected).strip()
    return ParsedResponse(markdown=markdown, groups=tuple(groups))


def render_response(
    source: str,
    *,
    console: Console | None = None,
    file: TextIO | None = None,
) -> tuple[Elicitation, ...]:
    """Render Markdown and follow-up choices; return choices for terminal input."""
    if console is None:
        # Android/proot terminals can report a misleading width to Rich.
        # Pin the renderer to the actual terminal column count so Markdown
        # paragraphs wrap before reaching the physical right edge.
        terminal_width = max(20, shutil.get_terminal_size(fallback=(80, 24)).columns)
        console = Console(file=file or sys.stdout, width=terminal_width, highlight=False)

    parsed = parse_response(source)
    if parsed.markdown:
        console.print(Markdown(parsed.markdown, code_theme="monokai"))

    choice_number = 1
    for group in parsed.groups:
        lines: list[Text] = []
        if group.message:
            lines.append(Text(group.message, style="bold"))
            lines.append(Text(""))
        for option in group.options:
            lines.append(Text(f"{choice_number}. ", style="bold cyan") + Text(option.label))
            choice_number += 1
        console.print(Panel.fit(Group(*lines), title="Next actions", border_style="cyan"))

    return parsed.options


def resolve_elicitation_selection(
    message: str, options: tuple[Elicitation, ...] | list[Elicitation]
) -> Elicitation | None:
    """Resolve a numeric choice or /choose N command to its exact query."""
    candidate = message.strip()
    match = re.fullmatch(r"(?:/choose\s+)?([1-9]\d*)", candidate, re.IGNORECASE)
    if not match:
        return None
    index = int(match.group(1)) - 1
    if index >= len(options):
        return None
    return options[index]
