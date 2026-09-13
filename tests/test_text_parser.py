from pathlib import Path

from nl_file_search.config import AppConfig
from nl_file_search.parsers.text import TextParser, split_text, window


def test_markdown_splits_on_headings() -> None:
    text = "# Intro\n\nHello\n\n## Details\n\nMore"
    sections = split_text(text, markdown=True)
    assert sections[0][0] == "Intro"
    assert "Hello" in sections[0][1]
    assert sections[1][0] == "Details"


def test_window_respects_max() -> None:
    parts = window("aaaa\n\nbbbb\n\ncccc", max_chars=6, overlap=0)
    assert all(len(p) <= 6 for p in parts)
    assert len(parts) >= 2


def test_text_parser_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("# Title\n\nBody text here.", encoding="utf-8")
    chunks = TextParser().parse(path, AppConfig())
    assert chunks
    assert chunks[0].modality == "text"
    assert "Body" in (chunks[0].text or "")
