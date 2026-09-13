"""Shared search used by the CLI and MCP."""

from __future__ import annotations

from nl_file_search.config import AppConfig
from nl_file_search.embed import Embedder
from nl_file_search.security import safe_resolve
from nl_file_search.store import SearchHit, VectorStore


def search_index(
    cfg: AppConfig,
    store: VectorStore,
    embedder: Embedder,
    query: str,
    *,
    k: int = 8,
    modality: str | None = None,
) -> list[SearchHit]:
    query = query.strip()
    if not query:
        raise ValueError("query is empty")
    allowed = {None, "text", "image", "video", "pdf"}
    if modality not in allowed:
        raise ValueError(f"modality must be one of text, image, video, pdf")
    vector = embedder.embed_query(query)
    return store.search(vector, k=k, modality=modality)


def get_indexed_file(store: VectorStore, path: str) -> dict:
    """Return indexed metadata/text only. Refuses paths not already ingested."""
    try:
        resolved = str(safe_resolve(path))
    except OSError:
        resolved = path
    record = store.get_file_by_path(resolved)
    if record is None:
        record = store.get_file_by_path(path)
    if record is None:
        return {
            "ok": False,
            "error": "Path is not in the index. Search first, then pass a hit path.",
        }
    chunks = store.chunks_for_path(record.path)
    payload_chunks = []
    for chunk in chunks:
        item: dict = {
            "chunk_index": chunk.chunk_index,
            "modality": chunk.modality,
            "title": chunk.title,
            "heading": chunk.heading,
        }
        if chunk.modality == "text" or chunk.text:
            text = chunk.text or ""
            item["text"] = text[:4000]
        if chunk.page_start is not None:
            item["page_start"] = chunk.page_start
            item["page_end"] = chunk.page_end
        if chunk.time_start is not None:
            item["time_start"] = chunk.time_start
            item["time_end"] = chunk.time_end
        payload_chunks.append(item)
    return {
        "ok": True,
        "path": record.path,
        "mime": record.mime,
        "parser": record.parser,
        "status": record.status,
        "chunks": payload_chunks,
    }


def hit_to_dict(hit: SearchHit, snippet_chars: int = 400) -> dict:
    snippet = None
    if hit.text:
        snippet = hit.text[:snippet_chars]
    return {
        "path": hit.path,
        "score": round(hit.score, 4),
        "distance": round(hit.distance, 4),
        "modality": hit.modality,
        "title": hit.title,
        "heading": hit.heading,
        "snippet": snippet,
        "page_start": hit.page_start,
        "page_end": hit.page_end,
        "time_start": hit.time_start,
        "time_end": hit.time_end,
        "chunk_index": hit.chunk_index,
    }
