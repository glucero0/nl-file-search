"""User-profile data directory (outside the repo)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR_NAME = "nl-file-search"


def user_data_dir() -> Path:
    return Path.home() / APP_DIR_NAME


def config_path() -> Path:
    return user_data_dir() / "config.yaml"


def env_path() -> Path:
    return user_data_dir() / ".env"


def index_path() -> Path:
    return user_data_dir() / "index.sqlite"


def logs_dir() -> Path:
    return user_data_dir() / "logs"


STARTER_CONFIG = """\
# Folders to index. Unknown extensions are skipped.
sources: []
  # - path: "D:\\\\Notes"
exclude: []
embed:
  model: gemini-embedding-2
  dimensions: 768
video:
  max_seconds: 120
"""

STARTER_ENV = """\
# Gemini API key. Never copy this file into the git repo.
GEMINI_API_KEY=
"""


def ensure_user_data_dir() -> Path:
    """Create the profile directory, starter config, and empty .env if missing."""
    root = user_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    cfg = config_path()
    if not cfg.exists():
        cfg.write_text(STARTER_CONFIG, encoding="utf-8")
    env = env_path()
    if not env.exists():
        env.write_text(STARTER_ENV, encoding="utf-8")
    return root


def load_user_env() -> None:
    """Load GEMINI_API_KEY from the profile .env. Does not override a real env var."""
    ensure_user_data_dir()
    load_dotenv(env_path(), override=False)


def require_api_key() -> str:
    load_user_env()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "GEMINI_API_KEY is missing. Set it in "
            f"{env_path()} or in the environment. Do not put the key in the repo."
        )
    return key
