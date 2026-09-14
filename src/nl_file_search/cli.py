"""nl-search command-line interface."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from nl_file_search.config import load_config
from nl_file_search.embed import Embedder
from nl_file_search.ingest import ingest
from nl_file_search.paths import ensure_logs_dir, index_path, logs_dir, require_api_key
from nl_file_search.search import get_indexed_file, hit_to_dict, search_index
from nl_file_search.security import safe_resolve
from nl_file_search.store import VectorStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nl-search", description="Index and search local files")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Scan sources and update the index")
    ingest_p.add_argument("--path", action="append", default=[], help="Extra/only root to scan")
    ingest_p.add_argument(
        "--no-purge",
        action="store_true",
        help="Do not remove index rows for files that disappeared",
    )

    search_p = sub.add_parser("search", help="Natural-language search")
    search_p.add_argument("query", nargs="+")
    search_p.add_argument("-k", type=int, default=8)
    search_p.add_argument(
        "--modality",
        choices=("text", "image", "video", "pdf"),
        default=None,
    )
    search_p.add_argument("--json", action="store_true")

    sub.add_parser("status", help="Show index counts and recent errors")

    get_p = sub.add_parser("get", help="Show indexed chunks for a path")
    get_p.add_argument("path")

    args = parser.parse_args(argv)
    try:
        cfg = load_config()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _setup_logging()

    if args.command == "ingest":
        api_key = require_api_key()
        extra = [safe_resolve(p) for p in args.path] or None
        with VectorStore(index_path(), cfg.embed.dimensions) as store:
            embedder = Embedder(api_key, cfg.embed)
            stats = ingest(
                cfg,
                store,
                embedder,
                extra_roots=extra,
                purge=not args.no_purge,
            )
        print(json.dumps(stats, indent=2))
        return 0 if stats["errors"] == 0 else 1

    if args.command == "search":
        api_key = require_api_key()
        query = " ".join(args.query)
        with VectorStore(index_path(), cfg.embed.dimensions) as store:
            embedder = Embedder(api_key, cfg.embed)
            hits = search_index(
                cfg, store, embedder, query, k=args.k, modality=args.modality
            )
        payload = [hit_to_dict(h) for h in hits]
        if args.json:
            print(json.dumps(payload, indent=2))
        elif not payload:
            print("No matches.")
        else:
            for index, hit in enumerate(payload, start=1):
                loc = _location(hit)
                print(f"{index}. {hit['score']:.3f}  [{hit['modality']}]  {hit['path']}{loc}")
                if hit["snippet"]:
                    print(f"   {hit['snippet'].replace(chr(10), ' ')[:200]}")
        return 0

    if args.command == "status":
        if not index_path().exists():
            print("Index does not exist yet. Run nl-search ingest.")
            return 0
        with VectorStore(index_path(), cfg.embed.dimensions) as store:
            print(json.dumps(store.status_summary(), indent=2))
        return 0

    if args.command == "get":
        if not index_path().exists():
            print("Index does not exist yet. Run nl-search ingest.")
            return 1
        with VectorStore(index_path(), cfg.embed.dimensions) as store:
            print(json.dumps(get_indexed_file(store, args.path), indent=2))
        return 0

    return 2


def _location(hit: dict) -> str:
    if hit.get("page_start"):
        return f"  p.{hit['page_start']}"
    if hit.get("time_start") is not None:
        return f"  {hit['time_start']:.1f}-{hit['time_end']:.1f}s"
    if hit.get("heading"):
        return f"  #{hit['heading']}"
    return ""


def _setup_logging() -> None:
    ensure_logs_dir()
    log_file = logs_dir() / "nl-search.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


if __name__ == "__main__":
    raise SystemExit(main())
