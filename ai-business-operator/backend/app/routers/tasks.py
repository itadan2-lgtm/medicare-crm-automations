"""Task inspection and the human-approval endpoints.

Approval is reachable only with a user token — `get_current_user` rejects service
tokens, so an agent cannot release its own hold.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Project, Task, User
from app.schemas import TaskRead, TaskStatus
from app.security import get_current_user
from app.services.events import EventBus
from app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _owned_task(task_id: int, user: User, session: AsyncSession) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    project = await session.get(Project, task.project_id)
    if project is None or project.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    stmt = (
        select(Task)
        .join(Project, Project.project_id == Task.project_id)
        .where(Project.user_id == user.user_id)
        .order_by(Task.task_id.desc())
    )
    if task_status is not None:
        stmt = stmt.where(Task.status == task_status.value)
    return list((await session.execute(stmt)).scalars())


@router.get("/pending-approval", response_model=list[TaskRead])
async def pending_approval(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    """Everything parked at the human gate — the dashboard's review queue."""
    stmt = (
        select(Task)
        .join(Project, Project.project_id == Task.project_id)
        .where(
            Project.user_id == user.user_id,
            Task.status == TaskStatus.AWAITING_APPROVAL.value,
        )
        .order_by(Task.task_id)
    )
    return list((await session.execute(stmt)).scalars())


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    return await _owned_task(task_id, user, session)


@router.post("/{task_id}/approve", response_model=TaskRead)
async def approve_task(
    task_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    await _owned_task(task_id, user, session)
    bus = EventBus.from_env()
    try:
        return await Orchestrator(session, bus).approve_task(task_id, user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        await bus.aclose()


@router.post("/{task_id}/reject", response_model=TaskRead)
async def reject_task(
    task_id: int,
    reason: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Task:
    await _owned_task(task_id, user, session)
    try:
        return await Orchestrator(session).reject_task(task_id, user.user_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
