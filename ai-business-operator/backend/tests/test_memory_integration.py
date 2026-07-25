"""Vector memory against real pgvector.

The store's SQL does things a fake cannot check: casting a Python list into
`vector`, cosine distance ordering, and the expiry/model filters that keep stale or
mismatched embeddings out of recall.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import requires_db
from vector_memory.embeddings import HashEmbedder
from vector_memory.store import PgVectorStore

pytestmark = requires_db


def store_for(session: AsyncSession, ttl_days: int = 365) -> PgVectorStore:
    # HashEmbedder keeps this offline and deterministic. Neighbour *quality* is a
    # property of the embedding model; what's under test is the storage and
    # retrieval path around it.
    return PgVectorStore(session, HashEmbedder(dimensions=1536), ttl_days=ttl_days)


async def test_remember_then_recall(session: AsyncSession, project: int) -> None:
    store = store_for(session)
    await store.remember(
        content="lack of motivation for home workouts",
        category="customer_pain",
        project_id=project,
        agent_name="research_agent",
        metadata={"topic": "fitness"},
    )

    hits = await store.recall(
        query="lack of motivation for home workouts", category="customer_pain"
    )

    assert len(hits) == 1
    assert hits[0].content == "lack of motivation for home workouts"
    assert hits[0].metadata == {"topic": "fitness"}
    assert hits[0].similarity > 0.99  # identical text, identical vector


async def test_recall_orders_by_similarity(session: AsyncSession, project: int) -> None:
    store = store_for(session)
    for content in ("no time to exercise", "cannot stay motivated", "gym is too expensive"):
        await store.remember(
            content=content,
            category="customer_pain",
            project_id=project,
            agent_name="research_agent",
        )

    hits = await store.recall(query="cannot stay motivated", category="customer_pain", top_k=3)

    assert len(hits) == 3
    assert hits[0].content == "cannot stay motivated"
    assert hits[0].similarity >= hits[1].similarity >= hits[2].similarity


async def test_recall_filters_by_category(session: AsyncSession, project: int) -> None:
    store = store_for(session)
    await store.remember(
        content="a pain", category="customer_pain", project_id=project, agent_name="research_agent"
    )
    await store.remember(
        content="a headline", category="headline", project_id=project, agent_name="copy_agent"
    )

    assert [h.content for h in await store.recall(query="a", category="headline")] == ["a headline"]


async def test_recall_can_scope_to_one_project(session: AsyncSession, project: int) -> None:
    from app.models import Project

    other = Project(user_id=(await session.get(Project, project)).user_id, name="Other", goal="x")
    session.add(other)
    await session.flush()

    store = store_for(session)
    await store.remember(
        content="mine", category="headline", project_id=project, agent_name="copy_agent"
    )
    await store.remember(
        content="theirs", category="headline", project_id=other.project_id, agent_name="copy_agent"
    )

    scoped = await store.recall(query="x", category="headline", project_id=project)
    assert [h.content for h in scoped] == ["mine"]

    everything = await store.recall(query="x", category="headline")
    assert {h.content for h in everything} == {"mine", "theirs"}


async def test_expired_records_are_not_recalled(session: AsyncSession, project: int) -> None:
    """Retention is enforced at read time as well as by the purge job, so an
    unpurged record cannot leak back into a prompt."""
    store = store_for(session)
    record_id = await store.remember(
        content="stale insight", category="headline", project_id=project, agent_name="copy_agent"
    )
    await session.execute(
        text("UPDATE memory_records SET expires_at = :past WHERE id = :id"),
        {"past": datetime.now(UTC) - timedelta(days=1), "id": record_id},
    )

    assert await store.recall(query="stale insight", category="headline") == []


async def test_important_records_never_expire(session: AsyncSession, project: int) -> None:
    store = store_for(session)
    record_id = await store.remember(
        content="keep me",
        category="headline",
        project_id=project,
        agent_name="copy_agent",
        important=True,
    )

    expires_at = await session.scalar(
        text("SELECT expires_at FROM memory_records WHERE id = :id"), {"id": record_id}
    )
    assert expires_at is None


async def test_ttl_is_applied_to_ordinary_records(session: AsyncSession, project: int) -> None:
    record_id = await store_for(session, ttl_days=30).remember(
        content="temporary", category="headline", project_id=project, agent_name="copy_agent"
    )

    expires_at = await session.scalar(
        text("SELECT expires_at FROM memory_records WHERE id = :id"), {"id": record_id}
    )
    assert expires_at is not None
    assert 29 <= (expires_at - datetime.now(UTC)).days <= 30


async def test_recall_ignores_other_embedding_models(session: AsyncSession, project: int) -> None:
    """Mixing models returns neighbours that look plausible and are not comparable,
    so rows from a previous model are inert rather than wrong."""
    store = store_for(session)
    record_id = await store.remember(
        content="from an older model",
        category="headline",
        project_id=project,
        agent_name="copy_agent",
    )
    await session.execute(
        text("UPDATE memory_records SET embedding_model = 'ancient-v0' WHERE id = :id"),
        {"id": record_id},
    )

    assert await store.recall(query="from an older model", category="headline") == []


async def test_purge_expired_deletes_only_expired_unimportant_rows(
    session: AsyncSession, project: int
) -> None:
    store = store_for(session)
    stale = await store.remember(
        content="stale", category="headline", project_id=project, agent_name="copy_agent"
    )
    await store.remember(
        content="fresh", category="headline", project_id=project, agent_name="copy_agent"
    )
    await store.remember(
        content="important",
        category="headline",
        project_id=project,
        agent_name="copy_agent",
        important=True,
    )
    await session.execute(
        text("UPDATE memory_records SET expires_at = :past WHERE id = :id"),
        {"past": datetime.now(UTC) - timedelta(days=1), "id": stale},
    )

    assert await store.purge_expired() == 1
    remaining = await session.scalar(
        text("SELECT count(*) FROM memory_records WHERE project_id = :p"), {"p": project}
    )
    assert remaining == 2


async def test_forget_removes_a_single_record(session: AsyncSession, project: int) -> None:
    store = store_for(session)
    record_id = await store.remember(
        content="delete me", category="headline", project_id=project, agent_name="copy_agent"
    )

    await store.forget(record_id)

    assert await store.recall(query="delete me", category="headline") == []


async def test_forget_project_clears_all_its_memory(session: AsyncSession, project: int) -> None:
    """Users control their own memory: deleting a project takes its memory with it."""
    store = store_for(session)
    for i in range(3):
        await store.remember(
            content=f"item {i}", category="headline", project_id=project, agent_name="copy_agent"
        )

    assert await store.forget_project(project) == 3
    assert await store.recall(query="item", category="headline", project_id=project) == []
