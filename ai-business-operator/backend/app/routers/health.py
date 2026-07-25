"""Liveness and readiness probes, plus Prometheus metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Deliberately does not touch the database."""
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}


@router.get("/ready")
async def ready(response: Response, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Readiness: dependencies reachable. Kubernetes pulls the pod from the
    service on failure rather than restarting it."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any failure as not-ready
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "database": type(exc).__name__}
    return {"status": "ready", "database": "ok"}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
