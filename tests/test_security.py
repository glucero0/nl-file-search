from pathlib import Path

from nl_file_search.config import AppConfig, should_skip_file
from nl_file_search.search import get_indexed_file
from nl_file_search.security import is_secret_path
from nl_file_search.store import VectorStore


def test_secret_names_are_detected(tmp_path: Path) -> None:
    assert is_secret_path(tmp_path / ".env")
    assert is_secret_path(tmp_path / ".env.local")
    assert is_secret_path(tmp_path / "id_rsa")
    assert is_secret_path(tmp_path / "server.pem")
    assert is_secret_path(tmp_path / "credentials.json")
    assert is_secret_path(tmp_path / "client_secret_abc.json")
    assert not is_secret_path(tmp_path / "notes.md")


def test_data_dir_files_are_skipped(tmp_path: Path) -> None:
    data = tmp_path / "nl-file-search"
    data.mkdir()
    secret = data / "index.sqlite"
    secret.write_bytes(b"x")
    cfg = AppConfig(data_dir=data)
    assert should_skip_file(secret, cfg)


def test_get_file_refuses_unknown_path(tmp_path: Path) -> None:
    db = tmp_path / "index.sqlite"
    store = VectorStore(db, 768)
    try:
        result = get_indexed_file(store, str(tmp_path / "not-indexed.md"))
        assert result["ok"] is False
    finally:
        store.close()
