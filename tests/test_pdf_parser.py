from pathlib import Path

from pypdf import PdfWriter

from nl_file_search.config import AppConfig
from nl_file_search.parsers.pdf import PdfParser


def test_pdf_splits_pages(tmp_path: Path) -> None:
    dest = tmp_path / "two.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with dest.open("wb") as handle:
        writer.write(handle)
    chunks = PdfParser().parse(dest, AppConfig())
    assert len(chunks) == 2
    assert chunks[0].page_start == 1
    assert chunks[1].page_start == 2
    assert chunks[0].media_mime == "application/pdf"
    assert chunks[0].media_bytes
