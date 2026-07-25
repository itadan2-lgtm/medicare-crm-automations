"""Adapts the CEO agent into the `Planner` callable the orchestrator expects.

Lives in `agents/` rather than `backend/` so the API process can validate a plan
without importing agent or LLM code — the orchestrator only ever sees a callable.
"""

from __future__ import annotations

import logging

from agents.base.llm import LLM, ClaudeLLM
from agents.loader import load_agent
from app.config import get_settings
from app.schemas import ProjectPlan

log = logging.getLogger(__name__)


def build_planner(llm: LLM | None = None):  # noqa: ANN201 - returns the Planner callable
    """Return an async callable that turns a goal into a candidate ProjectPlan.

    The result is a *proposal*. `Orchestrator.plan_project` validates it against the
    agent registry and falls back to the fixed template if it does not hold up.
    """
    settings = get_settings()

    if llm is None:
        if not settings.anthropic_api_key:
            # No key means no planning. Returning None makes the orchestrator use
            # the template, which is the right behaviour rather than a failure.
            log.info("planner.unavailable", extra={"reason": "ANTHROPIC_API_KEY not set"})
            return None
        llm = ClaudeLLM(settings.anthropic_api_key, settings.anthropic_model)

    agent = load_agent("ceo_agent", llm)

    async def plan(goal: str) -> ProjectPlan:
        output = await agent.run({"goal": goal})
        return ProjectPlan.model_validate(output)

    return plan
