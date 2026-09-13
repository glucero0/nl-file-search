"""Parser plugin types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nl_file_search.config import AppConfig


@dataclass(frozen=True)
class ParsedChunk:
    modality: str
    text: str | None = None
    title: str | None = None
    heading: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    time_start: float | None = None
    time_end: float | None = None
    media_bytes: bytes | None = None
    media_mime: str | None = None


class Parser(Protocol):
    name: str
    extensions: tuple[str, ...]
    mime: str

    def parse(self, path: Path, cfg: AppConfig) -> list[ParsedChunk]:
        ...
