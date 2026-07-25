"""Long-term memory over pgvector.

`VectorStore` is the interface agents depend on. `PgVectorStore` is the
implementation; swapping in Chroma or Pinecone later means writing another class
here, not touching agent code.

Retention: records expire after `ttl_days` unless marked important. Memory belongs
to the project owner and is deletable by them — nothing is retained indefinitely by
default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vector_memory.embeddings import Embedder

log = logging.getLogger(__name__)


@dataclass
class MemoryHit:
    id: int
    content: str
    category: str
    similarity: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    async def remember(
        self,
        *,
        content: str,
        category: str,
        project_id: int | None = None,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        important: bool = False,
    ) -> int: ...

    async def recall(
        self,
        *,
        query: str,
        category: str | None = None,
        project_id: int | None = None,
        top_k: int = 5,
    ) -> list[MemoryHit]: ...


class PgVectorStore:
    def __init__(self, session: AsyncSession, embedder: Embedder, ttl_days: int = 365) -> None:
        self.session = session
        self.embedder = embedder
        self.ttl_days = ttl_days

    async def remember(
        self,
        *,
        content: str,
        category: str,
        project_id: int | None = None,
        agent_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        important: bool = False,
    ) -> int:
        embedding = await self.embedder.embed(content)
        # Important records never expire; everything else is time-bound.
        expires_at = None if important else datetime.now(UTC) + timedelta(days=self.ttl_days)

        result = await self.session.execute(
            text(
                """
                INSERT INTO memory_records
                    (project_id, agent_name, category, content, embedding,
                     embedding_model, metadata, is_important, expires_at)
                VALUES
                    (:project_id, :agent_name, :category, :content, :embedding,
                     :embedding_model, CAST(:metadata AS jsonb), :important, :expires_at)
                RETURNING id
                """
            ),
            {
                "project_id": project_id,
                "agent_name": agent_name,
                "category": category,
                "content": content,
                "embedding": _to_pgvector(embedding),
                "embedding_model": self.embedder.model_name,
                "metadata": _to_json(metadata or {}),
                "important": important,
                "expires_at": expires_at,
            },
        )
        record_id = int(result.scalar_one())
        log.info(
            "memory.written",
            extra={"memory_id": record_id, "category": category, "agent": agent_name},
        )
        return record_id

    async def recall(
        self,
        *,
        query: str,
        category: str | None = None,
        project_id: int | None = None,
        top_k: int = 5,
    ) -> list[MemoryHit]:
        """Cosine-similarity search, newest-valid records only.

        Only rows embedded with the current model are considered — mixing models
        would return neighbours that look plausible and are not comparable.
        """
        embedding = await self.embedder.embed(query)

        result = await self.session.execute(
            text(
                """
                SELECT id, content, category, metadata,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM memory_records
                WHERE embedding IS NOT NULL
                  AND embedding_model = :embedding_model
                  AND (expires_at IS NULL OR expires_at > NOW())
                  -- The casts are required, not cosmetic: asyncpg cannot infer a
                  -- parameter's type from a bare IS NULL and errors out without them.
                  AND (CAST(:category AS text) IS NULL OR category = CAST(:category AS text))
                  AND (
                      CAST(:project_id AS integer) IS NULL
                      OR project_id = CAST(:project_id AS integer)
                  )
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            ),
            {
                "embedding": _to_pgvector(embedding),
                "embedding_model": self.embedder.model_name,
                "category": category,
                "project_id": project_id,
                "top_k": top_k,
            },
        )

        return [
            MemoryHit(
                id=row.id,
                content=row.content,
                category=row.category,
                similarity=float(row.similarity),
                metadata=row.metadata or {},
            )
            for row in result
        ]

    async def forget(self, memory_id: int) -> None:
        """Hard delete. Users control their own memory."""
        await self.session.execute(
            text("DELETE FROM memory_records WHERE id = :id"), {"id": memory_id}
        )
        log.info("memory.deleted", extra={"memory_id": memory_id})

    async def forget_project(self, project_id: int) -> int:
        result = await self.session.execute(
            text("DELETE FROM memory_records WHERE project_id = :pid"), {"pid": project_id}
        )
        return result.rowcount or 0

    async def purge_expired(self) -> int:
        """Delete time-expired records. Run on a schedule."""
        result = await self.session.execute(
            text(
                "DELETE FROM memory_records "
                "WHERE is_important = FALSE AND expires_at IS NOT NULL AND expires_at <= NOW()"
            )
        )
        count = result.rowcount or 0
        if count:
            log.info("memory.purged", extra={"deleted": count})
        return count


def _to_pgvector(values: list[float]) -> str:
    """pgvector's text input format: '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def _to_json(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload)
