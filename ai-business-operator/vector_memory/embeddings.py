"""Embedding generation.

One model for both writes and reads — a mixed-model index returns confidently wrong
neighbours. The model name is stored on every row so drift is detectable rather than
silent; changing `EMBEDDING_MODEL` requires a re-index.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from typing import Protocol

log = logging.getLogger(__name__)


class Embedder(Protocol):
    model_name: str
    dimensions: int

    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """Embeddings via the OpenAI API."""

    def __init__(self, api_key: str, model: str, dimensions: int = 1536) -> None:
        self.model_name = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._client: object | None = None

    def _ensure_client(self) -> object:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise RuntimeError("openai package is not installed") from exc
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._ensure_client()
        response = await client.embeddings.create(  # type: ignore[attr-defined]
            model=self.model_name, input=texts
        )
        return [item.embedding for item in response.data]


class HashEmbedder:
    """Deterministic local embedder for tests and offline development.

    Produces a stable pseudo-random vector per input. Nearest-neighbour results are
    meaningless — this exists so the storage and retrieval paths can be exercised
    without a network call or an API key, not to approximate semantics.
    """

    model_name = "hash-embedder-v1"

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha512(text.encode("utf-8")).digest()
        values: list[float] = []
        while len(values) < self.dimensions:
            digest = hashlib.sha512(digest).digest()
            for offset in range(0, len(digest) - 3, 4):
                if len(values) >= self.dimensions:
                    break
                (raw,) = struct.unpack_from(">I", digest, offset)
                values.append((raw / 0xFFFFFFFF) * 2 - 1)

        norm = sum(v * v for v in values) ** 0.5
        return [v / norm for v in values] if norm else values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(text) for text in texts]


def build_embedder(
    *, api_key: str = "", model: str = "text-embedding-3-small", dimensions: int = 1536
) -> Embedder:
    """Pick an embedder. Falls back to the local one when no key is configured,
    so development and tests work offline."""
    if api_key:
        return OpenAIEmbedder(api_key, model, dimensions)
    log.warning(
        "embeddings.using_hash_fallback",
        extra={
            "hint": "Set OPENAI_API_KEY for real embeddings; similarity is meaningless without it"
        },
    )
    return HashEmbedder(dimensions)
