"""Gemini Embedding 2 client. One Content per request item."""

from __future__ import annotations

import logging
import math
import time
from typing import Sequence

from google import genai
from google.genai import types

from nl_file_search.config import EmbedSettings

log = logging.getLogger(__name__)


def prepare_query(query: str) -> str:
    return f"task: search result | query: {query}"


def prepare_document(content: str, title: str | None = None) -> str:
    heading = title if title else "none"
    return f"title: {heading} | text: {content}"


def _l2_normalize(values: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 0:
        return list(values)
    return [v / norm for v in values]


class Embedder:
    def __init__(self, api_key: str, settings: EmbedSettings) -> None:
        self._client = genai.Client(api_key=api_key)
        self.settings = settings

    def embed_query(self, query: str) -> list[float]:
        return self._embed_text(prepare_query(query))

    def embed_document(self, text: str, title: str | None = None) -> list[float]:
        return self._embed_text(prepare_document(text, title))

    def embed_bytes(self, data: bytes, mime_type: str) -> list[float]:
        part = types.Part.from_bytes(data=data, mime_type=mime_type)
        content = types.Content(parts=[part])
        return self._request([content])

    def _embed_text(self, text: str) -> list[float]:
        part = types.Part.from_text(text=text)
        content = types.Content(parts=[part])
        return self._request([content])

    def _request(self, contents: list[types.Content]) -> list[float]:
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                result = self._client.models.embed_content(
                    model=self.settings.model,
                    contents=contents,
                    config=types.EmbedContentConfig(
                        output_dimensionality=self.settings.dimensions
                    ),
                )
                embeddings = result.embeddings or []
                if not embeddings or not embeddings[0].values:
                    raise RuntimeError("Gemini returned no embedding values")
                values = list(embeddings[0].values)
                if len(values) != self.settings.dimensions:
                    raise RuntimeError(
                        f"Expected {self.settings.dimensions} dims, got {len(values)}"
                    )
                return _l2_normalize(values)
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                retryable = any(
                    token in message
                    for token in ("429", "500", "503", "unavailable", "resource exhausted")
                )
                if not retryable or attempt == 4:
                    raise
                delay = 2 ** attempt
                log.warning("Embed retry in %ss after: %s", delay, exc)
                time.sleep(delay)
        raise RuntimeError(last_error)
