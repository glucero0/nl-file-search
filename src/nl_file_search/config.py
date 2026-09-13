"""Load %USERPROFILE%\\nl-file-search\\config.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from nl_file_search.paths import config_path, ensure_user_data_dir
from nl_file_search.security import is_secret_path, is_skipped_dir_name, is_under_data_dir, safe_resolve


@dataclass(frozen=True)
class EmbedSettings:
    model: str = "gemini-embedding-2"
    dimensions: int = 768


@dataclass(frozen=True)
class VideoSettings:
    max_seconds: int = 120


@dataclass(frozen=True)
class AppConfig:
    sources: list[Path] = field(default_factory=list)
    exclude_globs: list[str] = field(default_factory=list)
    embed: EmbedSettings = field(default_factory=EmbedSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    data_dir: Path = field(default_factory=lambda: Path.home() / "nl-file-search")


def load_config() -> AppConfig:
    ensure_user_data_dir()
    raw_path = config_path()
    raw: dict = {}
    if raw_path.exists():
        loaded = yaml.safe_load(raw_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config must be a mapping: {raw_path}")
        raw = loaded

    sources: list[Path] = []
    for item in raw.get("sources") or []:
        if isinstance(item, str):
            sources.append(safe_resolve(item))
        elif isinstance(item, dict) and item.get("path"):
            sources.append(safe_resolve(item["path"]))

    exclude = [str(g) for g in (raw.get("exclude") or [])]
    embed_raw = raw.get("embed") or {}
    video_raw = raw.get("video") or {}
    dims = int(embed_raw.get("dimensions", 768))
    if dims not in (128, 256, 512, 768, 1536, 3072) and not (128 <= dims <= 3072):
        raise ValueError("embed.dimensions must be between 128 and 3072")
    return AppConfig(
        sources=sources,
        exclude_globs=exclude,
        embed=EmbedSettings(
            model=str(embed_raw.get("model", "gemini-embedding-2")),
            dimensions=dims,
        ),
        video=VideoSettings(max_seconds=int(video_raw.get("max_seconds", 120))),
        data_dir=raw_path.parent,
    )


def path_matches_exclude(path: Path, exclude_globs: list[str]) -> bool:
    as_posix = path.as_posix()
    name = path.name
    for pattern in exclude_globs:
        if path.match(pattern) or Path(as_posix).match(pattern):
            return True
        # Path.match is relative; also try name-only globs like **/*.pem
        if Path(name).match(pattern) or Path(name).match(pattern.removeprefix("**/")):
            return True
    return False


def should_skip_file(path: Path, cfg: AppConfig) -> bool:
    if is_secret_path(path):
        return True
    if is_under_data_dir(path, cfg.data_dir):
        return True
    if path_matches_exclude(path, cfg.exclude_globs):
        return True
    return False


def should_skip_dir(path: Path, cfg: AppConfig) -> bool:
    if is_skipped_dir_name(path.name):
        return True
    if path_matches_exclude(path, cfg.exclude_globs):
        return True
    return False
