"""Adapter exposing the browser agent through the standard loader.

The implementation lives in the top-level `browser_agent/` package because it runs
as its own deployment with a Playwright base image, tighter network policy, and no
LLM or database credentials. This module is the thin seam the worker loads.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import BrowserResult


class BrowserAgentAdapter(BaseAgent):
    agent_name = "browser_agent"
    output_model = BrowserResult

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        # This agent has no `llm` in its allowed tools and never prompts a model —
        # it executes a plan another agent already produced.
        raise NotImplementedError(
            "browser_agent does not use an LLM. Run it via `python -m browser_agent.agent`."
        )

    async def run(self, task_input: dict[str, Any]) -> dict[str, Any]:
        from browser_agent.runner import execute_task

        result = await execute_task(task_input)
        return result.model_dump()
