"""Skip credential-like files and junk directories. Never send these to Gemini."""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".hg",
        ".svn",
    }
)

_SECRET_NAMES = frozenset(
    {
        ".env",
        ".netrc",
        "netrc",
        "credentials.json",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        ".npmrc",
        ".pypirc",
    }
)

_SECRET_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".keystore",
    ".jks",
)

_SECRET_NAME_RE = re.compile(
    r"(^|.*)(credential|secret|passwd|password)s?(\.|$)",
    re.IGNORECASE,
)

_ENV_NAME_RE = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)


def is_secret_path(path: Path) -> bool:
    name = path.name
    lowered = name.lower()
    if lowered in _SECRET_NAMES:
        return True
    if _ENV_NAME_RE.match(name):
        return True
    if lowered.endswith(_SECRET_SUFFIXES):
        return True
    if lowered.endswith(".json") and "client_secret" in lowered:
        return True
    if _SECRET_NAME_RE.search(name):
        return True
    return False


def is_skipped_dir_name(name: str) -> bool:
    return name.lower() in {n.lower() for n in DEFAULT_SKIP_DIR_NAMES}


def is_under_data_dir(path: Path, data_dir: Path) -> bool:
    try:
        path.resolve().relative_to(data_dir.resolve())
        return True
    except ValueError:
        return False


def safe_resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()
