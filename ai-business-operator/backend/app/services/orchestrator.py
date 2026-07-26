"""The CEO agent's machinery: goal decomposition, task claiming, dependency
resolution, retries, and the human-approval gate.

This is the only module that creates tasks. Agents emit events; the orchestrator
decides what happens next. See CLAUDE.md rule 2.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import HUMAN_APPROVAL_REQUIRED, get_settings
from app.models import Task
from app.schemas import EventType, ProjectPlan, TaskCreate, TaskResult, TaskStatus
from app.services.events import EventBus
from app.services.planning import (
    AgentCapabilities,
    PlanRejected,
    to_launch_plan,
    validate_plan,
)

log = logging.getLogger(__name__)

#: Produces a candidate task graph from a goal. Supplied by the caller so the
#: orchestrator stays free of any dependency on agent or LLM code.
Planner = Callable[[str], Awaitable[ProjectPlan]]


# The Phase 1 launch plan: a fixed dependency graph covering research → published
# funnel. Each entry is (task_type, agent, list of indices in this same list that
# must finish first).
#
# TODO(phase-3): replace this fixed template with LLM-driven decomposition, so the
# CEO can plan around goals that don't fit the standard launch shape. The template
# stays as the fallback when decomposition fails validation.
LAUNCH_PLAN: list[tuple[str, str, list[int]]] = [
    ("research_market", "research_agent", []),
    ("create_product", "product_agent", [0]),
    ("create_brand", "branding_agent", [0]),
    ("write_copy", "copy_agent", [0, 1, 2]),
    ("plan_funnel", "funnel_agent", [1, 3]),
    ("write_emails", "email_agent", [1, 3]),
    ("build_pages", "browser_agent", [4]),
    ("configure_automations", "automation_agent", [5, 6]),
    ("publish_funnel", "browser_agent", [6, 7]),
    ("collect_analytics", "analytics_agent", [8]),
]

# Which event each task type emits when it completes successfully.
COMPLETION_EVENTS: dict[str, EventType] = {
    "research_market": EventType.MARKET_RESEARCH_DONE,
    "create_product": EventType.PRODUCT_DRAFTED,
    "create_brand": EventType.BRANDING_DONE,
    "write_copy": EventType.COPY_DONE,
    "plan_funnel": EventType.FUNNEL_PLANNED,
    "write_emails": EventType.EMAILS_DRAFTED,
    "configure_automations": EventType.AUTOMATIONS_READY,
    "build_pages": EventType.PAGES_BUILT,
    "collect_analytics": EventType.ANALYTICS_READY,
    "propose_optimizations": EventType.OPTIMIZATION_PROPOSED,
}


class Orchestrator:
    def __init__(self, session: AsyncSession, bus: EventBus | None = None) -> None:
        self.session = session
        self.bus = bus
        self.settings = get_settings()

    # --- Planning ----------------------------------------------------------

    async def plan_project(
        self, project_id: int, goal: str, planner: Planner | None = None
    ) -> list[Task]:
        """Create the initial task graph for a project.

        With a planner, the CEO agent proposes a graph and it is validated against
        the agent registry before any row is written. Without one — or when the
        proposal fails validation — the fixed LAUNCH_PLAN is used. Falling back is
        the normal, expected path, not an error state: a standard launch is well
        served by the template, and a plan that cannot be verified must not run.
        """
        plan = await self._resolve_plan(goal, planner)
        return await self._materialise(project_id, goal, plan)

    async def _resolve_plan(
        self, goal: str, planner: Planner | None
    ) -> list[tuple[str, str, list[int]]]:
        if planner is None:
            return LAUNCH_PLAN

        try:
            proposed = await planner(goal)
            capabilities = AgentCapabilities.from_registry()
            validated = validate_plan(proposed, capabilities)
            log.info("plan.accepted", extra={"task_count": len(validated)})
            return to_launch_plan(validated)
        except PlanRejected as exc:
            log.warning("plan.rejected", extra={"reason": str(exc)})
        except Exception as exc:  # noqa: BLE001 - planning must never block a project
            log.warning("plan.failed", extra={"error": f"{type(exc).__name__}: {exc}"[:300]})
        return LAUNCH_PLAN

    async def _materialise(
        self, project_id: int, goal: str, plan: list[tuple[str, str, list[int]]]
    ) -> list[Task]:
        """Write a plan to the tasks table.

        Dependencies are resolved to real task ids after the flush, since they're
        only known once rows exist.
        """
        created: list[Task] = []
        for task_type, agent, dep_indices in plan:
            task = Task(
                project_id=project_id,
                task_type=task_type,
                assigned_to=agent,
                status=TaskStatus.PENDING.value,
                # Root tasks carry the goal; the rest receive their context from
                # upstream outputs via _propagate_outputs.
                input={"goal": goal} if not dep_indices else {},
                depends_on=[],
            )
            self.session.add(task)
            created.append(task)

        await self.session.flush()  # assigns task_id

        for task, (_, _, dep_indices) in zip(created, plan, strict=True):
            task.depends_on = [created[i].task_id for i in dep_indices]

        await self.session.flush()
        log.info(
            "project.planned",
            extra={"project_id": project_id, "task_count": len(created)},
        )
        return created

    async def create_task(self, spec: TaskCreate) -> Task:
        task = Task(
            project_id=spec.project_id,
            task_type=spec.task_type,
            assigned_to=spec.assigned_to,
            input=spec.input,
            depends_on=spec.depends_on,
            status=TaskStatus.PENDING.value,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    # --- Claiming ----------------------------------------------------------

    async def claim_next_task(self, agent_name: str, worker_id: str) -> Task | None:
        """Atomically claim one runnable task for an agent.

        `FOR UPDATE SKIP LOCKED` lets several workers of the same agent type run
        without ever handing the same row to two of them. A task is runnable only
        once every id in `depends_on` has status 'done'.
        """
        stmt = text(
            """
            WITH claimable AS (
                SELECT t.task_id
                FROM tasks t
                WHERE t.assigned_to = :agent
                  AND t.status = 'pending'
                  AND NOT EXISTS (
                      SELECT 1 FROM unnest(t.depends_on) AS dep_id
                      JOIN tasks d ON d.task_id = dep_id
                      WHERE d.status <> 'done'
                  )
                ORDER BY t.task_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE tasks
            SET status = 'claimed',
                claimed_by = :worker_id,
                claimed_at = NOW(),
                updated_at = NOW()
            WHERE task_id IN (SELECT task_id FROM claimable)
            RETURNING task_id
            """
        )
        result = await self.session.execute(stmt, {"agent": agent_name, "worker_id": worker_id})
        row = result.first()
        if row is None:
            return None

        # populate_existing because the UPDATE above is raw SQL: without it the
        # identity map would hand back a stale copy of a task this session has
        # already loaded, with the previous claim's worker id still on it.
        task = await self.session.get(Task, row.task_id, populate_existing=True)
        if task is None:
            return None

        # The approval gate sits between claiming and working, so the worker never
        # begins an irreversible action it would then have to unwind.
        if self.requires_approval(task.task_type) and task.approved_at is None:
            task.status = TaskStatus.AWAITING_APPROVAL.value
            await self.session.flush()
            log.info(
                "task.awaiting_approval",
                extra={"task_id": task.task_id, "task_type": task.task_type},
            )
            if self.bus:
                await self.bus.publish(
                    EventType.APPROVAL_REQUESTED,
                    project_id=task.project_id,
                    agent=agent_name,
                    task_id=task.task_id,
                )
            return None

        task.status = TaskStatus.WORKING.value
        await self.session.flush()
        log.info("task.claimed", extra={"task_id": task.task_id, "agent": agent_name})
        return task

    def requires_approval(self, task_type: str) -> bool:
        return self.settings.require_human_approval and task_type in HUMAN_APPROVAL_REQUIRED

    # --- Completion --------------------------------------------------------

    async def complete_task(self, result: TaskResult) -> Task:
        task = await self.session.get(Task, result.task_id)
        if task is None:
            raise ValueError(f"Unknown task {result.task_id}")

        task.updated_at = datetime.now(UTC)

        if result.success:
            task.status = TaskStatus.DONE.value
            task.output = result.output
            task.error = None
            log.info(
                "task.done",
                extra={"task_id": task.task_id, "agent": result.agent},
            )
            if self.bus:
                event = COMPLETION_EVENTS.get(task.task_type, EventType.TASK_COMPLETED)
                await self.bus.publish(
                    event,
                    project_id=task.project_id,
                    agent=result.agent,
                    task_id=task.task_id,
                    result=result.output,
                )
            await self._propagate_outputs(task)
        else:
            task.attempts += 1
            task.error = result.error
            if not result.retryable:
                # Nothing about waiting or trying again changes a missing key or an
                # empty credit balance. Block now so the remaining tasks don't each
                # burn their attempts against the same wall.
                task.status = TaskStatus.BLOCKED.value
                log.error(
                    "task.blocked_permanently",
                    extra={
                        "task_id": task.task_id,
                        "agent": result.agent,
                        "error": (result.error or "")[:200],
                    },
                )
            elif task.attempts > self.settings.max_task_attempts:
                task.status = TaskStatus.BLOCKED.value
                log.error(
                    "task.blocked",
                    extra={
                        "task_id": task.task_id,
                        "agent": result.agent,
                        "attempts": task.attempts,
                    },
                )
            else:
                # Back to pending so another worker retries; the error travels with
                # it so the agent can see what went wrong last time.
                task.status = TaskStatus.PENDING.value
                task.claimed_by = None
                task.claimed_at = None
                log.warning(
                    "task.retrying",
                    extra={"task_id": task.task_id, "attempts": task.attempts},
                )
            if self.bus:
                await self.bus.publish(
                    EventType.TASK_FAILED,
                    project_id=task.project_id,
                    agent=result.agent,
                    task_id=task.task_id,
                    result={"error": result.error},
                )

        await self.session.flush()
        return task

    async def _propagate_outputs(self, task: Task) -> None:
        """Copy a finished task's output into the input of its dependents.

        Agents receive their upstream context this way rather than querying for it,
        which keeps their database scope to their own row.
        """
        stmt = select(Task).where(
            Task.project_id == task.project_id,
            Task.depends_on.any(task.task_id),
        )
        for dependent in (await self.session.execute(stmt)).scalars():
            merged = dict(dependent.input)
            merged[task.task_type] = task.output
            dependent.input = merged
        await self.session.flush()

    # --- Approval ----------------------------------------------------------

    async def approve_task(self, task_id: int, user_id: int) -> Task:
        """Release a human-approval hold. Only reachable from a user session."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Unknown task {task_id}")
        if task.status != TaskStatus.AWAITING_APPROVAL.value:
            raise ValueError(f"Task {task_id} is {task.status}, not awaiting approval")

        task.approved_by = user_id
        task.approved_at = datetime.now(UTC)
        task.status = TaskStatus.PENDING.value
        task.claimed_by = None
        task.claimed_at = None
        await self.session.flush()

        log.info("task.approved", extra={"task_id": task_id, "user_id": user_id})
        if self.bus:
            await self.bus.publish(
                EventType.APPROVAL_GRANTED,
                project_id=task.project_id,
                agent="ceo_agent",
                task_id=task_id,
            )
        return task

    async def reject_task(self, task_id: int, user_id: int, reason: str | None = None) -> Task:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Unknown task {task_id}")
        task.status = TaskStatus.CANCELLED.value
        task.error = reason or "Rejected by user"
        task.approved_by = user_id
        task.updated_at = datetime.now(UTC)
        await self.session.flush()
        log.info("task.rejected", extra={"task_id": task_id, "user_id": user_id})
        return task
