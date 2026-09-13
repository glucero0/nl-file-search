"""FastMCP stdio server for Cursor."""

from __future__ import annotations

from nl_file_search.config import load_config
from nl_file_search.embed import Embedder
from nl_file_search.paths import index_path, require_api_key
from nl_file_search.search import get_indexed_file, hit_to_dict, search_index
from nl_file_search.store import VectorStore

from fastmcp import FastMCP

mcp = FastMCP(
    "nl-file-search",
    instructions=(
        "Search the user's local nl-file-search index with natural language. "
        "Call search_files first when they ask about indexed files, notes, "
        "images, videos, or PDFs. Use get_file only for a path already returned "
        "by search. Do not invent file contents."
    ),
)


def _open() -> tuple:
    cfg = load_config()
    api_key = require_api_key()
    store = VectorStore(index_path(), cfg.embed.dimensions)
    embedder = Embedder(api_key, cfg.embed)
    return cfg, store, embedder


@mcp.tool
def search_files(query: str, k: int = 8, modality: str | None = None) -> list[dict]:
    """Search the local file index with natural language.

    Use this first when the user asks to find notes, images, videos, PDFs,
    or other files that may have been ingested by nl-search.
    modality may be text, image, video, or pdf.
    """
    cfg, store, embedder = _open()
    try:
        hits = search_index(cfg, store, embedder, query, k=k, modality=modality)
        return [hit_to_dict(hit) for hit in hits]
    finally:
        store.close()


@mcp.tool
def get_file(path: str) -> dict:
    """Return indexed text or media metadata for a path already in the index.

    Does not read arbitrary disk paths. Pass a path from search_files.
    Media results include path and page/time range, not binary bytes.
    """
    cfg = load_config()
    store = VectorStore(index_path(), cfg.embed.dimensions)
    try:
        return get_indexed_file(store, path)
    finally:
        store.close()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
