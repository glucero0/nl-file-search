"""PDF parser: one page per embed."""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from nl_file_search.config import AppConfig
from nl_file_search.parsers.base import ParsedChunk


class PdfParser:
    name = "pdf"
    extensions = (".pdf",)
    mime = "application/pdf"

    def parse(self, path: Path, cfg: AppConfig) -> list[ParsedChunk]:
        reader = PdfReader(str(path))
        title = path.stem
        chunks: list[ParsedChunk] = []
        for index, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            buf = io.BytesIO()
            writer.write(buf)
            page_no = index + 1
            text = (page.extract_text() or "").strip() or None
            chunks.append(
                ParsedChunk(
                    modality="pdf",
                    text=text,
                    title=title,
                    heading=f"page {page_no}",
                    page_start=page_no,
                    page_end=page_no,
                    media_bytes=buf.getvalue(),
                    media_mime="application/pdf",
                )
            )
        if not chunks:
            raise RuntimeError(f"PDF has no pages: {path}")
        return chunks
