"""SQLite + sqlite-vec index."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import sqlite_vec
from sqlite_vec import serialize_float32

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    mime TEXT,
    parser TEXT,
    status TEXT NOT NULL DEFAULT 'ok',
    last_error TEXT,
    last_ingested REAL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    modality TEXT NOT NULL,
    text TEXT,
    title TEXT,
    heading TEXT,
    page_start INTEGER,
    page_end INTEGER,
    time_start REAL,
    time_end REAL,
    UNIQUE (file_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class FileRecord:
    id: int
    path: str
    sha256: str
    mtime: float
    size: int
    mime: str | None
    parser: str | None
    status: str
    last_error: str | None


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    file_id: int
    chunk_index: int
    modality: str
    text: str | None
    title: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    time_start: float | None
    time_end: float | None


@dataclass(frozen=True)
class SearchHit:
    path: str
    score: float
    distance: float
    modality: str
    text: str | None
    title: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    time_start: float | None
    time_end: float | None
    chunk_index: int


class VectorStore:
    def __init__(self, db_path: Path, dimensions: int) -> None:
        self.db_path = db_path
        self.dimensions = dimensions
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        try:
            self.conn.enable_load_extension(True)
            sqlite_vec.load(self.conn)
            self.conn.enable_load_extension(False)
        except Exception as exc:
            raise RuntimeError(
                "Could not load the sqlite-vec extension. "
                "Use an official CPython build that allows load_extension."
            ) from exc
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> VectorStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        existing = self.conn.execute(
            "SELECT value FROM meta WHERE key = 'dimensions'"
        ).fetchone()
        if existing and int(existing["value"]) != self.dimensions:
            raise RuntimeError(
                f"Index was created with {existing['value']} dimensions; "
                f"config asks for {self.dimensions}. Delete "
                f"{self.db_path} to rebuild."
            )
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('dimensions', ?)",
            (str(self.dimensions),),
        )
        self.conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                embedding float[{self.dimensions}] distance_metric=cosine
            )
            """
        )
        self.conn.commit()

    def get_file_by_path(self, path: str) -> FileRecord | None:
        row = self.conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()
        return _file_from_row(row) if row else None

    def upsert_file(
        self,
        *,
        path: str,
        sha256: str,
        mtime: float,
        size: int,
        mime: str | None,
        parser: str | None,
        status: str = "ok",
        last_error: str | None = None,
        last_ingested: float,
    ) -> int:
        existing = self.get_file_by_path(path)
        if existing:
            self.conn.execute(
                """
                UPDATE files
                SET sha256 = ?, mtime = ?, size = ?, mime = ?, parser = ?,
                    status = ?, last_error = ?, last_ingested = ?
                WHERE id = ?
                """,
                (
                    sha256,
                    mtime,
                    size,
                    mime,
                    parser,
                    status,
                    last_error,
                    last_ingested,
                    existing.id,
                ),
            )
            self.conn.commit()
            return existing.id
        cur = self.conn.execute(
            """
            INSERT INTO files (
                path, sha256, mtime, size, mime, parser, status, last_error, last_ingested
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (path, sha256, mtime, size, mime, parser, status, last_error, last_ingested),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def mark_file_error(self, file_id: int, error: str, last_ingested: float) -> None:
        self.conn.execute(
            """
            UPDATE files
            SET status = 'error', last_error = ?, last_ingested = ?
            WHERE id = ?
            """,
            (error[:2000], last_ingested, file_id),
        )
        self.conn.commit()

    def replace_chunks(
        self,
        file_id: int,
        chunks: Iterable[tuple[ChunkRecord, Sequence[float]]],
    ) -> None:
        old_ids = [
            row["id"]
            for row in self.conn.execute(
                "SELECT id FROM chunks WHERE file_id = ?", (file_id,)
            )
        ]
        for chunk_id in old_ids:
            self.conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (chunk_id,))
        self.conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
        for chunk, vector in chunks:
            cur = self.conn.execute(
                """
                INSERT INTO chunks (
                    file_id, chunk_index, modality, text, title, heading,
                    page_start, page_end, time_start, time_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    chunk.chunk_index,
                    chunk.modality,
                    chunk.text,
                    chunk.title,
                    chunk.heading,
                    chunk.page_start,
                    chunk.page_end,
                    chunk.time_start,
                    chunk.time_end,
                ),
            )
            rowid = int(cur.lastrowid)
            self.conn.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (rowid, serialize_float32(list(vector))),
            )
        self.conn.commit()

    def delete_file(self, file_id: int) -> None:
        old_ids = [
            row["id"]
            for row in self.conn.execute(
                "SELECT id FROM chunks WHERE file_id = ?", (file_id,)
            )
        ]
        for chunk_id in old_ids:
            self.conn.execute("DELETE FROM vec_chunks WHERE rowid = ?", (chunk_id,))
        self.conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        self.conn.commit()

    def all_file_paths(self) -> list[str]:
        return [
            row["path"]
            for row in self.conn.execute("SELECT path FROM files ORDER BY path")
        ]

    def search(
        self,
        vector: Sequence[float],
        *,
        k: int = 8,
        modality: str | None = None,
    ) -> list[SearchHit]:
        k = max(1, min(k, 50))
        total = self.conn.execute("SELECT COUNT(*) AS n FROM vec_chunks").fetchone()["n"]
        if total == 0:
            return []
        fetch = min(50, k * 4 if modality else k)
        vec_rows = self.conn.execute(
            """
            SELECT rowid, distance
            FROM vec_chunks
            WHERE embedding MATCH ?
              AND k = ?
            """,
            (serialize_float32(list(vector)), fetch),
        ).fetchall()
        hits: list[SearchHit] = []
        for vec_row in vec_rows:
            row = self.conn.execute(
                """
                SELECT
                    files.path AS path,
                    chunks.modality AS modality,
                    chunks.text AS text,
                    chunks.title AS title,
                    chunks.heading AS heading,
                    chunks.page_start AS page_start,
                    chunks.page_end AS page_end,
                    chunks.time_start AS time_start,
                    chunks.time_end AS time_end,
                    chunks.chunk_index AS chunk_index
                FROM chunks
                JOIN files ON files.id = chunks.file_id
                WHERE chunks.id = ?
                """,
                (vec_row["rowid"],),
            ).fetchone()
            if row is None:
                continue
            if modality and row["modality"] != modality:
                continue
            distance = float(vec_row["distance"])
            hits.append(
                SearchHit(
                    path=row["path"],
                    score=max(0.0, 1.0 - distance),
                    distance=distance,
                    modality=row["modality"],
                    text=row["text"],
                    title=row["title"],
                    heading=row["heading"],
                    page_start=row["page_start"],
                    page_end=row["page_end"],
                    time_start=row["time_start"],
                    time_end=row["time_end"],
                    chunk_index=int(row["chunk_index"]),
                )
            )
            if len(hits) >= k:
                break
        return hits

    def chunks_for_path(self, path: str) -> list[ChunkRecord]:
        rows = self.conn.execute(
            """
            SELECT chunks.*
            FROM chunks
            JOIN files ON files.id = chunks.file_id
            WHERE files.path = ?
            ORDER BY chunks.chunk_index
            """,
            (path,),
        ).fetchall()
        return [_chunk_from_row(row) for row in rows]

    def status_summary(self) -> dict:
        files = self.conn.execute("SELECT COUNT(*) AS n FROM files").fetchone()["n"]
        errors = self.conn.execute(
            "SELECT COUNT(*) AS n FROM files WHERE status = 'error'"
        ).fetchone()["n"]
        by_mod = {
            row["modality"]: row["n"]
            for row in self.conn.execute(
                "SELECT modality, COUNT(*) AS n FROM chunks GROUP BY modality"
            )
        }
        recent_errors = [
            {"path": row["path"], "error": row["last_error"]}
            for row in self.conn.execute(
                """
                SELECT path, last_error
                FROM files
                WHERE status = 'error'
                ORDER BY last_ingested DESC
                LIMIT 10
                """
            )
        ]
        return {
            "files": files,
            "error_files": errors,
            "chunks_by_modality": by_mod,
            "recent_errors": recent_errors,
        }


def _file_from_row(row: sqlite3.Row) -> FileRecord:
    return FileRecord(
        id=row["id"],
        path=row["path"],
        sha256=row["sha256"],
        mtime=row["mtime"],
        size=row["size"],
        mime=row["mime"],
        parser=row["parser"],
        status=row["status"],
        last_error=row["last_error"],
    )


def _chunk_from_row(row: sqlite3.Row) -> ChunkRecord:
    return ChunkRecord(
        id=row["id"],
        file_id=row["file_id"],
        chunk_index=row["chunk_index"],
        modality=row["modality"],
        text=row["text"],
        title=row["title"],
        heading=row["heading"],
        page_start=row["page_start"],
        page_end=row["page_end"],
        time_start=row["time_start"],
        time_end=row["time_end"],
    )
