"""Copy example config and .env into ~/nl-file-search. Does not overwrite."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FILES = (
    ("config.example.yaml", "config.yaml"),
    (".env.example", ".env"),
)


def profile_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / "nl-file-search"


def copy_examples(home: Path | None = None) -> int:
    dest = profile_dir(home)
    dest.mkdir(parents=True, exist_ok=True)
    for src_name, dest_name in FILES:
        src = REPO / src_name
        if not src.is_file():
            print(f"error: missing {src}", file=sys.stderr)
            return 1
        target = dest / dest_name
        if target.exists():
            print(f"already exists: {target}")
            continue
        shutil.copyfile(src, target)
        print(f"created: {target}")
    return 0


def main() -> int:
    return copy_examples()


if __name__ == "__main__":
    raise SystemExit(main())
