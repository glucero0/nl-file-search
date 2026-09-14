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


def missing_config_message(path: Path | None = None) -> str:
    target = path or config_path()
    return (
        f"Missing {target}. Copy config.example.yaml to that path from the repo "
        "(see README Setup). nl-search does not create config.yaml or .env."
    )


def ensure_logs_dir() -> Path:
    """Create the log directory under an existing profile folder."""
    dest = logs_dir()
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def load_user_env() -> None:
    """Load GEMINI_API_KEY from the profile .env. Does not override a real env var."""
    env = env_path()
    if env.exists():
        load_dotenv(env, override=False)


def require_api_key() -> str:
    load_user_env()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        env = env_path()
        if not env.exists():
            raise SystemExit(
                f"Missing {env}. Copy .env.example to that path from the repo "
                "(see README Setup) and set GEMINI_API_KEY. Do not put the key in the repo."
            )
        raise SystemExit(
            "GEMINI_API_KEY is missing. Set it in "
            f"{env} or in the environment. Do not put the key in the repo."
        )
    return key
