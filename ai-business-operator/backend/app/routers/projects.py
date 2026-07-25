"""Project CRUD. Creating a project is what kicks off the whole pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Project, User
from app.schemas import ProjectCreate, ProjectRead, TaskRead
from app.security import get_current_user
from app.services.events import EventBus
from app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/projects", tags=["projects"])


async def _owned_project(project_id: int, user: User, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    # 404 rather than 403 for someone else's project — do not confirm it exists.
    if project is None or project.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Project:
    project = Project(
        user_id=user.user_id, name=payload.name, goal=payload.goal, niche=payload.niche
    )
    session.add(project)
    await session.flush()

    bus = EventBus.from_env()
    try:
        await Orchestrator(session, bus).plan_project(
            project.project_id, project.goal, planner=_planner()
        )
    finally:
        await bus.aclose()

    return project


def _planner():  # noqa: ANN202 - returns the optional Planner callable
    """Build the CEO planner if agent code is importable and a key is configured.

    The API can run without the agents package installed — a deployment that only
    serves the dashboard has no reason to carry LLM dependencies. In that case
    planning falls back to the fixed template.
    """
    try:
        from agents.planner import build_planner
    except ImportError:
        return None
    return build_planner()


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Project]:
    stmt = (
        select(Project).where(Project.user_id == user.user_id).order_by(Project.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars())


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Project:
    return await _owned_project(project_id, user, session)


@router.get("/{project_id}/tasks", response_model=list[TaskRead])
async def project_tasks(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    from app.models import Task  # local import keeps the router import graph shallow

    await _owned_project(project_id, user, session)
    stmt = select(Task).where(Task.project_id == project_id).order_by(Task.task_id)
    return list((await session.execute(stmt)).scalars())


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    project = await _owned_project(project_id, user, session)
    await session.delete(project)
