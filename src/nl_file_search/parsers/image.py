"""Image parser. PNG/JPEG native; convert WEBP/BMP/GIF; skip HEIC."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from nl_file_search.config import AppConfig
from nl_file_search.parsers.base import ParsedChunk

NATIVE = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
CONVERT = {".webp", ".bmp", ".gif"}
SKIP = {".heic", ".heif"}
MAX_BYTES = 20 * 1024 * 1024


class ImageParser:
    name = "image"
    extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
    mime = "image/jpeg"

    def parse(self, path: Path, cfg: AppConfig) -> list[ParsedChunk]:
        suffix = path.suffix.lower()
        if suffix in SKIP:
            raise RuntimeError(f"Skipping HEIC/HEIF (not Phase 1): {path}")
        if path.stat().st_size > MAX_BYTES:
            raise RuntimeError(f"Image larger than {MAX_BYTES} bytes: {path}")
        title = path.stem
        if suffix in NATIVE:
            data = path.read_bytes()
            mime = NATIVE[suffix]
        elif suffix in CONVERT:
            data, mime = _to_jpeg(path)
        else:
            raise RuntimeError(f"Unsupported image type: {suffix}")
        return [
            ParsedChunk(
                modality="image",
                title=title,
                media_bytes=data,
                media_mime=mime,
            )
        ]


def _to_jpeg(path: Path) -> tuple[bytes, str]:
    with Image.open(path) as img:
        frame = img.convert("RGB")
        buf = io.BytesIO()
        frame.save(buf, format="JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"
