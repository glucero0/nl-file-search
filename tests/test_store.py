from pathlib import Path

from nl_file_search.store import ChunkRecord, VectorStore


def test_upsert_and_search_roundtrip(tmp_path: Path) -> None:
    store = VectorStore(tmp_path / "index.sqlite", 8)
    try:
        file_id = store.upsert_file(
            path=str(tmp_path / "a.md"),
            sha256="abc",
            mtime=1.0,
            size=10,
            mime="text/plain",
            parser="text",
            last_ingested=1.0,
        )
        vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        chunk = ChunkRecord(
            id=0,
            file_id=file_id,
            chunk_index=0,
            modality="text",
            text="hello world",
            title="a",
            heading=None,
            page_start=None,
            page_end=None,
            time_start=None,
            time_end=None,
        )
        store.replace_chunks(file_id, [(chunk, vector)])
        hits = store.search(vector, k=1)
        assert hits
        assert hits[0].path.endswith("a.md")
        assert hits[0].text == "hello world"
    finally:
        store.close()
