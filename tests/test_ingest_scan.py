from pathlib import Path

from nl_file_search.config import AppConfig
from nl_file_search.ingest import iter_source_files


def test_scan_skips_secrets_and_unknown_types(tmp_path: Path) -> None:
    (tmp_path / "keep.md").write_text("hello", encoding="utf-8")
    (tmp_path / ".env").write_text("GEMINI_API_KEY=nope", encoding="utf-8")
    (tmp_path / "secret.pem").write_text("x", encoding="utf-8")
    (tmp_path / "notes.docx").write_text("office later", encoding="utf-8")
    nested = tmp_path / "node_modules"
    nested.mkdir()
    (nested / "pkg.md").write_text("skip me", encoding="utf-8")
    cfg = AppConfig(data_dir=tmp_path / "data")
    found = {p.name for p in iter_source_files(tmp_path, cfg)}
    assert found == {"keep.md"}
