"""Embedder behaviour and pgvector serialisation.

Similarity search itself needs a live Postgres with pgvector and is covered by the
integration suite (Phase 4).
"""

from __future__ import annotations

import pytest

from vector_memory.embeddings import HashEmbedder, build_embedder
from vector_memory.store import _to_pgvector


async def test_hash_embedder_is_deterministic() -> None:
    embedder = HashEmbedder(dimensions=64)
    first = await embedder.embed("lack of motivation for home workouts")
    second = await embedder.embed("lack of motivation for home workouts")
    assert first == second


async def test_hash_embedder_separates_inputs() -> None:
    embedder = HashEmbedder(dimensions=64)
    assert await embedder.embed("home fitness") != await embedder.embed("home cooking")


async def test_hash_embedder_returns_unit_vectors() -> None:
    embedder = HashEmbedder(dimensions=128)
    vector = await embedder.embed("some memory")
    assert len(vector) == 128
    assert pytest.approx(sum(v * v for v in vector) ** 0.5, abs=1e-6) == 1.0


async def test_embed_batch_matches_single() -> None:
    embedder = HashEmbedder(dimensions=32)
    batch = await embedder.embed_batch(["a", "b"])
    assert batch[0] == await embedder.embed("a")
    assert batch[1] == await embedder.embed("b")


def test_build_embedder_falls_back_offline() -> None:
    """No key must not mean no development. The fallback is loud in the logs."""
    assert isinstance(build_embedder(api_key=""), HashEmbedder)


def test_build_embedder_uses_openai_when_keyed() -> None:
    embedder = build_embedder(api_key="sk-test", model="text-embedding-3-small")
    assert embedder.model_name == "text-embedding-3-small"
    assert not isinstance(embedder, HashEmbedder)


def test_pgvector_serialisation_format() -> None:
    assert _to_pgvector([0.5, -0.25, 0.0]) == "[0.500000,-0.250000,0.000000]"


def test_model_name_is_recorded_for_drift_detection() -> None:
    """recall() filters on embedding_model, so the name must be stable per embedder."""
    assert HashEmbedder().model_name == "hash-embedder-v1"
