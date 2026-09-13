"""Split MP4/MOV into Gemini-sized clips with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from nl_file_search.config import AppConfig
from nl_file_search.parsers.base import ParsedChunk

FFMPEG_HINT = (
    "ffmpeg is required to index videos. Install it and ensure it is on PATH. "
    "On Windows: winget install Gyan.FFmpeg"
)


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(FFMPEG_HINT)
    return ffmpeg, ffprobe


class VideoParser:
    name = "video"
    extensions = (".mp4", ".mov")
    mime = "video/mp4"

    def parse(self, path: Path, cfg: AppConfig) -> list[ParsedChunk]:
        ffmpeg, ffprobe = require_ffmpeg()
        duration = _probe_duration(ffprobe, path)
        max_seconds = max(1, cfg.video.max_seconds)
        title = path.stem
        chunks: list[ParsedChunk] = []
        starts: list[float]
        if duration is None or duration <= 0:
            starts = [0.0]
            ends = [float(max_seconds)]
        else:
            starts = list(_frange(0.0, duration, max_seconds))
            ends = [min(start + max_seconds, duration) for start in starts]
        with tempfile.TemporaryDirectory(prefix="nl-search-video-") as tmp:
            tmp_dir = Path(tmp)
            for index, (start, end) in enumerate(zip(starts, ends, strict=True)):
                out = tmp_dir / f"chunk-{index:04d}.mp4"
                _cut_clip(ffmpeg, path, out, start, end - start)
                chunks.append(
                    ParsedChunk(
                        modality="video",
                        title=title,
                        heading=f"{start:.1f}s-{end:.1f}s",
                        time_start=start,
                        time_end=end,
                        media_bytes=out.read_bytes(),
                        media_mime="video/mp4",
                    )
                )
        return chunks


def _frange(start: float, stop: float, step: float) -> list[float]:
    values: list[float] = []
    current = start
    while current < stop:
        values.append(current)
        current += step
    return values or [start]


def _probe_duration(ffprobe: str, path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        text = result.stdout.strip()
        if not text or text.upper() == "N/A":
            return None
        return float(text)
    except (subprocess.CalledProcessError, ValueError):
        return None


def _cut_clip(ffmpeg: str, src: Path, dest: Path, start: float, length: float) -> None:
    copy_cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{length:.3f}",
        "-i",
        str(src),
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(dest),
    ]
    copied = subprocess.run(copy_cmd, capture_output=True, text=True)
    if copied.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
        return
    dest.unlink(missing_ok=True)
    encode_cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{length:.3f}",
        "-i",
        str(src),
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    encoded = subprocess.run(encode_cmd, capture_output=True, text=True)
    if encoded.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        detail = (encoded.stderr or copied.stderr or "ffmpeg failed").strip()
        raise RuntimeError(f"ffmpeg could not cut {src}: {detail[:500]}")
