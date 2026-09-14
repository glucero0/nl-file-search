"""Load ~/nl-file-search/config.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from nl_file_search.paths import config_path, missing_config_message
from nl_file_search.security import is_secret_path, is_skipped_dir_name, is_under_data_dir, safe_resolve

# Double-quoted YAML scalars. Used to find Windows paths before PyYAML scans escapes.
_DOUBLE_QUOTED = re.compile(r'"([^"\\]|\\.)*"')


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


def _has_lone_backslash(text: str) -> bool:
    index = 0
    length = len(text)
    while index < length:
        if text[index] == "\\":
            if index + 1 < length and text[index + 1] == "\\":
                index += 2
                continue
            return True
        index += 1
    return False


def _is_unescaped_windows_path(inner: str) -> bool:
    if not _has_lone_backslash(inner):
        return False
    if len(inner) >= 3 and inner[0].isalpha() and inner[1] == ":" and inner[2] == "\\":
        return True
    # Unescaped UNC share: \\server\folder
    if inner.startswith("\\\\") and _has_lone_backslash(inner[2:]):
        return True
    return False


def normalize_windows_paths_in_yaml(text: str) -> str:
    """Turn unescaped Windows paths in double quotes into forward slashes.

    YAML treats ``\\U``, ``\\t``, and ``\\n`` as escapes inside double quotes, so a
    path like ``"C:\\Users\\Notes"`` either fails to parse or is silently corrupted.
    Already-escaped paths (``C:\\\\Users``) and non-path strings are left alone.
    """

    def replace(match: re.Match[str]) -> str:
        quoted = match.group(0)
        inner = quoted[1:-1]
        if _is_unescaped_windows_path(inner):
            return '"' + inner.replace("\\", "/") + '"'
        return quoted

    return _DOUBLE_QUOTED.sub(replace, text)


def _windows_yaml_path_hint(config_file: Path) -> str:
    return (
        f"Could not parse {config_file}. Double-quoted YAML treats backslashes as "
        r"escapes, so Windows paths like "
        r'"C:\Users\..." fail. Use forward slashes (C:/Users/you/Notes), '
        r"single quotes ('C:\Users\you\Notes'), or doubled backslashes "
        r'("C:\\Users\\you\\Notes").'
    )


def load_config(path: Path | None = None) -> AppConfig:
    raw_path = path if path is not None else config_path()
    if not raw_path.exists():
        raise ValueError(missing_config_message(raw_path))
    prepared = normalize_windows_paths_in_yaml(raw_path.read_text(encoding="utf-8"))
    try:
        loaded = yaml.safe_load(prepared) or {}
    except yaml.YAMLError as exc:
        raise ValueError(_windows_yaml_path_hint(raw_path)) from exc
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
