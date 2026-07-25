"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import dispose_engine
from app.logging_config import configure_logging
from app.routers import auth, health, projects, tasks

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    log.info(
        "app.startup",
        extra={
            "environment": settings.environment,
            "dry_run": settings.dry_run,
            "require_human_approval": settings.require_human_approval,
        },
    )
    if settings.is_production and settings.dry_run:
        log.warning("app.dry_run_in_production", extra={"hint": "No systeme.io writes will occur"})
    yield
    await dispose_engine()
    log.info("app.shutdown")


app = FastAPI(
    title="AI Business Operator",
    description="Autonomous multi-agent system for researching, building and launching "
    "digital businesses on systeme.io.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Dashboard origin only. Widen deliberately, per environment — never to "*".
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "ai-business-operator", "docs": "/docs"}
