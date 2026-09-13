"""Markdown and plain-text chunking."""

from __future__ import annotations

import re
from pathlib import Path

from nl_file_search.config import AppConfig
from nl_file_search.parsers.base import ParsedChunk

# Stay well under Gemini's 8192-token input limit.
MAX_CHARS = 12_000
OVERLAP_CHARS = 200
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


class TextParser:
    name = "text"
    extensions = (".md", ".txt")
    mime = "text/plain"

    def parse(self, path: Path, cfg: AppConfig) -> list[ParsedChunk]:
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        title = path.stem
        pieces = split_text(text, path.suffix.lower() == ".md")
        chunks: list[ParsedChunk] = []
        for heading, body in pieces:
            if not body.strip():
                continue
            for part in window(body.strip(), MAX_CHARS, OVERLAP_CHARS):
                chunks.append(
                    ParsedChunk(
                        modality="text",
                        text=part,
                        title=title,
                        heading=heading,
                    )
                )
        return chunks


def split_text(text: str, markdown: bool) -> list[tuple[str | None, str]]:
    if not markdown:
        return [(None, text)]
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [(None, text)]
    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        heading = match.group(2).strip()
        sections.append((heading, f"{heading}\n\n{body}".strip()))
    return sections


def window(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            split_at = text.rfind("\n\n", start, end)
            if split_at <= start:
                split_at = text.rfind("\n", start, end)
            if split_at > start:
                end = split_at
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [p for p in parts if p]
