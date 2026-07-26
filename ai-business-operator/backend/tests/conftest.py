"""Shared fixtures.

Integration tests need a real Postgres with pgvector — the orchestrator's claim
query leans on `FOR UPDATE SKIP LOCKED`, array containment, and CTE-scoped locking,
none of which a sqlite stand-in reproduces. Faking them would test the fake.

Set `TEST_DATABASE_URL` to run them; without it they skip:

    createdb aibo_test
    TEST_DATABASE_URL=postgresql+asyncpg://user@localhost/aibo_test pytest
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL to a Postgres with pgvector to run integration tests",
)


@pytest_asyncio.fixture
async def engine():  # noqa: ANN201
    """Function-scoped deliberately.

    asyncpg binds connections to the event loop that opened them, and pytest-asyncio
    gives each test its own loop. A session-scoped engine leaks connections across
    loops and fails with "another operation is in progress". Engine construction is
    cheap and NullPool means no connection is held between tests.
    """
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    # Reset committed state. Most tests are isolated by the rollback in `session`,
    # but the concurrency test needs real transactions and leaves rows behind, and
    # anything run manually against this database does too. Claiming is
    # deliberately global across projects — a worker serves the whole queue — so a
    # stray pending task silently changes what a claim returns.
    #
    # TEST_DATABASE_URL must point at a dedicated test database: this is
    # destructive. `agents` is preserved; it is seeded by the migration and tasks
    # reference it.
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE memory_records, analytics_snapshots, tasks, funnel_steps, "
                "funnels, emails, products, projects, users RESTART IDENTITY CASCADE"
            )
        )

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:  # noqa: ANN001
    """A session whose writes are rolled back at the end of each test.

    Everything happens inside one outer transaction that is never committed, so
    tests share a schema without sharing state and none of them need cleanup.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        maker = async_sessionmaker(bind=connection, expire_on_commit=False)
        async with maker() as session:
            yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def user_id(session: AsyncSession) -> int:
    """A real user row. Tasks reference users via approved_by, so approval tests
    need an id that actually exists rather than a hardcoded 1."""
    from app.models import User

    user = User(email=f"test-{uuid4().hex[:12]}@example.test", password_hash="x")
    session.add(user)
    await session.flush()
    return user.user_id


@pytest_asyncio.fixture
async def project(session: AsyncSession, user_id: int) -> int:
    from app.models import Project

    project = Project(user_id=user_id, name="Test", goal="fitness ebook business")
    session.add(project)
    await session.flush()
    return project.project_id
