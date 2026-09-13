"""Parser registry. Phase 2/3 add modules here without changing ingest."""

from __future__ import annotations

from pathlib import Path

from nl_file_search.parsers.base import ParsedChunk, Parser
from nl_file_search.parsers.image import ImageParser
from nl_file_search.parsers.pdf import PdfParser
from nl_file_search.parsers.text import TextParser
from nl_file_search.parsers.video import VideoParser

_PARSERS: tuple[Parser, ...] = (
    TextParser(),
    ImageParser(),
    PdfParser(),
    VideoParser(),
)

_BY_EXT: dict[str, Parser] = {}
for _parser in _PARSERS:
    for _ext in _parser.extensions:
        _BY_EXT[_ext.lower()] = _parser


def parser_for(path: Path) -> Parser | None:
    return _BY_EXT.get(path.suffix.lower())


def registered_extensions() -> frozenset[str]:
    return frozenset(_BY_EXT)


__all__ = [
    "ParsedChunk",
    "Parser",
    "parser_for",
    "registered_extensions",
]
