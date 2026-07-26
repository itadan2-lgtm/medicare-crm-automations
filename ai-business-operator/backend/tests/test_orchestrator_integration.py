"""Orchestrator behaviour against a real Postgres.

Covers the parts that only a real database can prove: dependency-gated claiming,
SKIP LOCKED under concurrency, output propagation, the approval gate, and the
retry-to-blocked path.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import Task
from app.schemas import PlannedTask, ProjectPlan, TaskResult, TaskStatus
from app.services.orchestrator import LAUNCH_PLAN, Orchestrator
from tests.conftest import requires_db

pytestmark = requires_db


def orchestrator(session: AsyncSession, **overrides: object) -> Orchestrator:
    orch = Orchestrator(session, bus=None)
    if overrides:
        orch.settings = Settings(**overrides)  # type: ignore[arg-type]
    return orch


async def tasks_of(session: AsyncSession, project_id: int) -> list[Task]:
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.task_id)
    return list((await session.execute(stmt)).scalars())


# --- Planning --------------------------------------------------------------


async def test_plan_project_writes_the_launch_plan(session: AsyncSession, project: int) -> None:
    created = await orchestrator(session).plan_project(project, "fitness ebook")

    assert len(created) == len(LAUNCH_PLAN)
    assert created[0].task_type == "research_market"
    # Only root tasks carry the goal; the rest are filled by propagation.
    assert created[0].input == {"goal": "fitness ebook"}
    assert created[1].input == {}


async def test_plan_resolves_dependency_indices_to_real_ids(
    session: AsyncSession, project: int
) -> None:
    created = await orchestrator(session).plan_project(project, "fitness ebook")
    by_type = {t.task_type: t for t in created}

    # create_product depends on research_market (index 0 in LAUNCH_PLAN).
    assert by_type["create_product"].depends_on == [by_type["research_market"].task_id]


async def test_planner_output_is_used_when_valid(session: AsyncSession, project: int) -> None:
    async def planner(goal: str) -> ProjectPlan:
        return ProjectPlan(
            summary="short plan",
            tasks=[
                PlannedTask(task_type="research_market", assigned_to="research_agent"),
                PlannedTask(
                    task_type="write_copy", assigned_to="copy_agent", depends_on_indices=[0]
                ),
            ],
        )

    created = await orchestrator(session).plan_project(project, "fitness", planner=planner)
    assert [t.task_type for t in created] == ["research_market", "write_copy"]


async def test_invalid_planner_output_falls_back_to_the_template(
    session: AsyncSession, project: int
) -> None:
    """A plan that fails validation must not run — and must not block the project."""

    async def bad_planner(goal: str) -> ProjectPlan:
        return ProjectPlan(
            summary="nonsense",
            tasks=[PlannedTask(task_type="hack_the_gibson", assigned_to="research_agent")],
        )

    created = await orchestrator(session).plan_project(project, "fitness", planner=bad_planner)
    assert len(created) == len(LAUNCH_PLAN)


async def test_planner_exception_falls_back_to_the_template(
    session: AsyncSession, project: int
) -> None:
    async def exploding_planner(goal: str) -> ProjectPlan:
        raise RuntimeError("model unavailable")

    created = await orchestrator(session).plan_project(
        project, "fitness", planner=exploding_planner
    )
    assert len(created) == len(LAUNCH_PLAN)


# --- Claiming --------------------------------------------------------------


async def test_claim_returns_a_runnable_task(session: AsyncSession, project: int) -> None:
    await orchestrator(session).plan_project(project, "fitness")

    claimed = await orchestrator(session).claim_next_task("research_agent", "worker-1")

    assert claimed is not None
    assert claimed.task_type == "research_market"
    assert claimed.status == TaskStatus.WORKING.value
    assert claimed.claimed_by == "worker-1"


async def test_claim_skips_tasks_with_unfinished_dependencies(
    session: AsyncSession, project: int
) -> None:
    await orchestrator(session).plan_project(project, "fitness")

    # product_agent's task depends on research, which has not run.
    assert await orchestrator(session).claim_next_task("product_agent", "worker-1") is None


async def test_claim_unblocks_once_the_dependency_is_done(
    session: AsyncSession, project: int
) -> None:
    orch = orchestrator(session)
    await orch.plan_project(project, "fitness")

    research = await orch.claim_next_task("research_agent", "worker-1")
    assert research is not None
    await orch.complete_task(
        TaskResult(
            task_id=research.task_id,
            agent="research_agent",
            success=True,
            output={"niche": "fitness"},
        )
    )

    product = await orch.claim_next_task("product_agent", "worker-2")
    assert product is not None
    assert product.task_type == "create_product"


async def test_claim_returns_none_when_nothing_is_pending(
    session: AsyncSession, project: int
) -> None:
    assert await orchestrator(session).claim_next_task("research_agent", "worker-1") is None


async def test_concurrent_workers_never_get_the_same_task(engine) -> None:  # noqa: ANN001
    """The point of FOR UPDATE SKIP LOCKED.

    Runs on its own committed sessions rather than the rollback fixture, because
    separate concurrent transactions are the whole subject of the test — which also
    means this one has to clean up after itself.
    """
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as setup:
        from app.models import Project, User

        user = User(email=f"concurrent-{uuid4().hex[:12]}@example.test", password_hash="x")
        setup.add(user)
        await setup.flush()
        proj = Project(user_id=user.user_id, name="Concurrent", goal="fitness")
        setup.add(proj)
        await setup.flush()
        project_id = proj.project_id
        user_row_id = user.user_id

        # Three claimable tasks for one agent.
        for _ in range(3):
            setup.add(
                Task(
                    project_id=project_id,
                    task_type="research_market",
                    assigned_to="research_agent",
                    status=TaskStatus.PENDING.value,
                    input={},
                    depends_on=[],
                )
            )
        await setup.commit()

    async def claim(worker_id: str) -> int | None:
        async with maker() as session:
            task = await Orchestrator(session, bus=None).claim_next_task(
                "research_agent", worker_id
            )
            task_id = task.task_id if task else None
            await session.commit()
            return task_id

    try:
        claimed = await asyncio.gather(*(claim(f"worker-{i}") for i in range(5)))
        got = [t for t in claimed if t is not None]

        assert len(got) == 3, "every task should be claimed exactly once"
        assert len(set(got)) == 3, f"a task was handed to two workers: {got}"
    finally:
        async with maker() as cleanup:
            from app.models import User

            # Cascades to the project and its tasks.
            if (user := await cleanup.get(User, user_row_id)) is not None:
                await cleanup.delete(user)
                await cleanup.commit()


# --- Completion and propagation --------------------------------------------


async def test_completion_propagates_output_to_dependents(
    session: AsyncSession, project: int
) -> None:
    """Agents receive upstream context on their task input rather than querying for
    it, which keeps their database scope to their own row."""
    orch = orchestrator(session)
    await orch.plan_project(project, "fitness")

    research = await orch.claim_next_task("research_agent", "worker-1")
    assert research is not None
    report = {"niche": "home fitness", "pain_points": ["no time"]}
    await orch.complete_task(
        TaskResult(task_id=research.task_id, agent="research_agent", success=True, output=report)
    )

    product = next(t for t in await tasks_of(session, project) if t.task_type == "create_product")
    assert product.input["research_market"] == report


async def test_failure_retries_then_blocks(session: AsyncSession, project: int) -> None:
    orch = orchestrator(session, max_task_attempts=2)
    await orch.plan_project(project, "fitness")

    task = await orch.claim_next_task("research_agent", "worker-1")
    assert task is not None
    task_id = task.task_id

    for expected in (TaskStatus.PENDING, TaskStatus.PENDING, TaskStatus.BLOCKED):
        result = await orch.complete_task(
            TaskResult(task_id=task_id, agent="research_agent", success=False, error="LLM timeout")
        )
        assert result.status == expected.value

    assert result.attempts == 3
    assert result.error == "LLM timeout"


async def test_retried_task_is_claimable_again(session: AsyncSession, project: int) -> None:
    orch = orchestrator(session)
    await orch.plan_project(project, "fitness")

    first = await orch.claim_next_task("research_agent", "worker-1")
    assert first is not None
    await orch.complete_task(
        TaskResult(task_id=first.task_id, agent="research_agent", success=False, error="boom")
    )

    second = await orch.claim_next_task("research_agent", "worker-2")
    assert second is not None
    assert second.task_id == first.task_id
    assert second.claimed_by == "worker-2"


# --- Cascading deletes -----------------------------------------------------


async def test_deleting_a_project_removes_its_tasks(session: AsyncSession, project: int) -> None:
    """Regression: without passive_deletes the ORM tries to NULL tasks.project_id
    first, which fails against a NOT NULL column and makes DELETE /projects/{id}
    impossible for any project that has tasks — i.e. all of them."""
    from app.models import Project

    await orchestrator(session).plan_project(project, "fitness")
    assert len(await tasks_of(session, project)) == len(LAUNCH_PLAN)

    await session.delete(await session.get(Project, project))
    await session.flush()

    assert await tasks_of(session, project) == []


async def test_deleting_a_user_removes_their_projects(session: AsyncSession, user_id: int) -> None:
    from app.models import Project, User

    project = Project(user_id=user_id, name="Doomed", goal="x")
    session.add(project)
    await session.flush()
    project_id = project.project_id

    await session.delete(await session.get(User, user_id))
    await session.flush()

    # A SELECT rather than session.get(): the database cascade removed the row, but
    # the identity map still holds the object it loaded a moment ago.
    remaining = await session.execute(select(Project).where(Project.project_id == project_id))
    assert remaining.scalars().all() == []


# --- The approval gate -----------------------------------------------------


async def test_gated_task_parks_instead_of_running(session: AsyncSession, project: int) -> None:
    """The most important rail in the system: publishing waits for a human."""
    orch = orchestrator(session, require_human_approval=True)
    await orch.plan_project(project, "fitness")

    for task in await tasks_of(session, project):
        if task.task_type != "publish_funnel":
            task.status = TaskStatus.DONE.value
    await session.flush()

    claimed = await orch.claim_next_task("browser_agent", "worker-1")

    assert claimed is None, "a gated task must never be handed to a worker"
    publish = next(t for t in await tasks_of(session, project) if t.task_type == "publish_funnel")
    assert publish.status == TaskStatus.AWAITING_APPROVAL.value


async def test_approved_task_becomes_claimable(
    session: AsyncSession, project: int, user_id: int
) -> None:
    orch = orchestrator(session, require_human_approval=True)
    await orch.plan_project(project, "fitness")

    for task in await tasks_of(session, project):
        if task.task_type != "publish_funnel":
            task.status = TaskStatus.DONE.value
    await session.flush()

    await orch.claim_next_task("browser_agent", "worker-1")  # parks it
    publish = next(t for t in await tasks_of(session, project) if t.task_type == "publish_funnel")

    approved = await orch.approve_task(publish.task_id, user_id=user_id)
    assert approved.status == TaskStatus.PENDING.value
    assert approved.approved_by == user_id

    claimed = await orch.claim_next_task("browser_agent", "worker-1")
    assert claimed is not None
    assert claimed.task_id == publish.task_id


async def test_approving_a_task_that_is_not_waiting_is_rejected(
    session: AsyncSession, project: int, user_id: int
) -> None:
    orch = orchestrator(session)
    created = await orch.plan_project(project, "fitness")

    with pytest.raises(ValueError, match="not awaiting approval"):
        await orch.approve_task(created[0].task_id, user_id=user_id)


async def test_rejecting_cancels_the_task(
    session: AsyncSession, project: int, user_id: int
) -> None:
    orch = orchestrator(session)
    created = await orch.plan_project(project, "fitness")

    rejected = await orch.reject_task(created[0].task_id, user_id=user_id, reason="wrong niche")
    assert rejected.status == TaskStatus.CANCELLED.value
    assert rejected.error == "wrong niche"


async def test_gate_disabled_lets_publishing_through(session: AsyncSession, project: int) -> None:
    """Only an explicit config change opens the gate — nothing in the task flow."""
    orch = orchestrator(session, require_human_approval=False)
    await orch.plan_project(project, "fitness")

    for task in await tasks_of(session, project):
        if task.task_type != "publish_funnel":
            task.status = TaskStatus.DONE.value
    await session.flush()

    claimed = await orch.claim_next_task("browser_agent", "worker-1")
    assert claimed is not None
    assert claimed.task_type == "publish_funnel"


async def test_permanent_failure_blocks_without_retrying(
    session: AsyncSession, project: int
) -> None:
    """An exhausted key or empty balance is not fixed by trying again. Blocking on
    the first failure keeps the other tasks from each burning their attempts
    against the same wall."""
    orch = orchestrator(session, max_task_attempts=3)
    await orch.plan_project(project, "fitness")

    task = await orch.claim_next_task("research_agent", "worker-1")
    assert task is not None

    result = await orch.complete_task(
        TaskResult(
            task_id=task.task_id,
            agent="research_agent",
            success=False,
            error="PermanentLLMError: credit balance is too low",
            retryable=False,
        )
    )

    assert result.status == TaskStatus.BLOCKED.value
    assert result.attempts == 1  # blocked on the first try, not the fourth
