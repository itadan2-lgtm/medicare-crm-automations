"""CEO / Orchestrator Agent.

Reads: the user's goal and the current project state.
Writes: a ProjectPlan — the task graph the orchestrator materialises.

The fixed LAUNCH_PLAN in the orchestrator covers the standard launch shape.
This agent exists for goals that do not fit it, and for replanning after a
task blocks. TODO(phase-3): wire it into Orchestrator.plan_project as the
primary path, with LAUNCH_PLAN as the fallback when validation fails.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from agents.registry import REGISTRY
from app.schemas import ProjectPlan


class CEOAgent(BaseAgent):
    agent_name = "ceo_agent"
    output_model = ProjectPlan

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        goal = task_input.get("goal", "")
        blocked = task_input.get("blocked_tasks", [])

        parts = [f"Business goal: {goal}", "Break this into a task graph."]

        if blocked:
            parts.append(
                "These tasks are blocked and need a different approach:\n"
                + "\n".join(f"- {t}" for t in blocked)
            )

        parts.append(
            "Available agents and what they do:\n"
            + "\n".join(
                f"- {spec.name}: {spec.description} (handles: {', '.join(sorted(spec.task_types))})"
                for spec in REGISTRY.values()
                if spec.name != "ceo_agent"
            )
        )
        parts.append(
            "Return a JSON object: {summary, tasks: [{task_type, assigned_to, "
            "depends_on_indices}]}.\n"
            "task_type must be one an agent actually handles, and assigned_to must be "
            "that agent. depends_on_indices refers to positions earlier in your own "
            "task list — a task may never depend on a later one, or nothing will ever "
            "run."
        )
        return "\n\n".join(parts)
