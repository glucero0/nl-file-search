"""Scan configured folders, parse, embed, and upsert."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

from nl_file_search.config import AppConfig, should_skip_dir, should_skip_file
from nl_file_search.embed import Embedder
from nl_file_search.parsers import parser_for
from nl_file_search.parsers.base import ParsedChunk
from nl_file_search.parsers.video import VideoParser, require_ffmpeg
from nl_file_search.store import ChunkRecord, VectorStore

log = logging.getLogger(__name__)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def iter_source_files(root: Path, cfg: AppConfig) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        log.warning("Source does not exist: %s", root)
        return found
    if root.is_file():
        if parser_for(root) and not should_skip_file(root, cfg):
            found.append(root.resolve())
        return found
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not should_skip_dir(current / name, cfg)
        )
        for name in sorted(filenames):
            path = current / name
            if should_skip_file(path, cfg):
                continue
            if parser_for(path) is None:
                continue
            found.append(path.resolve())
    return found


def ingest(
    cfg: AppConfig,
    store: VectorStore,
    embedder: Embedder,
    *,
    extra_roots: list[Path] | None = None,
    purge: bool = True,
) -> dict[str, int]:
    roots = list(extra_roots) if extra_roots else list(cfg.sources)
    if not roots:
        raise SystemExit(
            "No source folders. Add sources to "
            f"{cfg.data_dir / 'config.yaml'} or pass --path."
        )

    files: list[Path] = []
    for root in roots:
        files.extend(iter_source_files(root, cfg))

    if any(isinstance(parser_for(path), VideoParser) for path in files):
        require_ffmpeg()

    stats = {"seen": 0, "skipped": 0, "updated": 0, "errors": 0, "purged": 0}
    seen_paths: set[str] = set()

    for path in files:
        stats["seen"] += 1
        path_key = str(path)
        seen_paths.add(path_key)
        parser = parser_for(path)
        if parser is None:
            continue
        try:
            st = path.stat()
        except OSError as exc:
            log.error("Cannot stat %s: %s", path, exc)
            stats["errors"] += 1
            continue
        digest = file_sha256(path)
        existing = store.get_file_by_path(path_key)
        if (
            existing
            and existing.sha256 == digest
            and existing.status == "ok"
            and existing.size == st.st_size
        ):
            stats["skipped"] += 1
            continue
        file_id = store.upsert_file(
            path=path_key,
            sha256=digest,
            mtime=st.st_mtime,
            size=st.st_size,
            mime=parser.mime,
            parser=parser.name,
            status="ok",
            last_error=None,
            last_ingested=time.time(),
        )
        try:
            parsed = parser.parse(path, cfg)
            if not parsed:
                raise RuntimeError("parser returned no chunks")
            prepared = _embed_chunks(embedder, parsed, path.stem)
            store.replace_chunks(file_id, prepared)
            stats["updated"] += 1
            log.info("Indexed %s (%s chunks)", path, len(prepared))
        except Exception as exc:
            store.mark_file_error(file_id, str(exc), time.time())
            log.error("Failed %s: %s", path, exc)
            stats["errors"] += 1

    if purge:
        stats["purged"] = _purge_missing(store, seen_paths, roots if extra_roots else None)
    return stats


def _embed_chunks(
    embedder: Embedder, parsed: list[ParsedChunk], fallback_title: str
) -> list[tuple[ChunkRecord, list[float]]]:
    out: list[tuple[ChunkRecord, list[float]]] = []
    for index, chunk in enumerate(parsed):
        title = chunk.title or fallback_title
        if chunk.media_bytes and chunk.media_mime:
            vector = embedder.embed_bytes(chunk.media_bytes, chunk.media_mime)
        elif chunk.text:
            vector = embedder.embed_document(chunk.text, title)
        else:
            raise RuntimeError("chunk has neither text nor media")
        record = ChunkRecord(
            id=0,
            file_id=0,
            chunk_index=index,
            modality=chunk.modality,
            text=chunk.text,
            title=title,
            heading=chunk.heading,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            time_start=chunk.time_start,
            time_end=chunk.time_end,
        )
        out.append((record, vector))
    return out


def _purge_missing(
    store: VectorStore,
    seen_paths: set[str],
    only_under: list[Path] | None,
) -> int:
    removed = 0
    for stored in store.all_file_paths():
        if stored in seen_paths:
            continue
        if only_under is not None and not _is_under_any(Path(stored), only_under):
            continue
        rec = store.get_file_by_path(stored)
        if rec:
            store.delete_file(rec.id)
            removed += 1
            log.info("Purged missing file %s", stored)
    return removed


def _is_under_any(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False
