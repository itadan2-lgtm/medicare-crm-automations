"""Validation for LLM-produced task graphs.

The CEO agent proposes a plan; nothing here trusts it. A plan is a set of
instructions the system will execute autonomously, so it is checked as adversarial
input: unknown task types, mismatched agents, forward or circular dependencies, and
any attempt to route an approval-gated action to an agent that would sidestep the
gate are all rejected.

A rejected plan is not an error — `Orchestrator.plan_project` falls back to the
fixed LAUNCH_PLAN, which is always valid. Failing safe beats failing loudly here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import HUMAN_APPROVAL_REQUIRED
from app.schemas import PlannedTask, ProjectPlan

log = logging.getLogger(__name__)

MAX_TASKS = 30


class PlanRejected(ValueError):
    """The proposed plan failed validation and must not be executed."""


@dataclass(frozen=True)
class AgentCapabilities:
    """What the validator knows about the agent roster.

    Passed in rather than imported so the backend does not depend on the agents
    package — the API process validates plans without loading agent code.
    """

    task_type_to_agent: dict[str, str]

    @classmethod
    def from_registry(cls) -> AgentCapabilities:
        from agents.registry import REGISTRY

        mapping = {
            task_type: spec.name for spec in REGISTRY.values() for task_type in spec.task_types
        }
        return cls(task_type_to_agent=mapping)


def validate_plan(plan: ProjectPlan, capabilities: AgentCapabilities) -> list[PlannedTask]:
    """Return the plan's tasks if every rule holds, else raise PlanRejected."""
    tasks = plan.tasks

    if not tasks:
        raise PlanRejected("Plan contains no tasks")
    if len(tasks) > MAX_TASKS:
        raise PlanRejected(f"Plan has {len(tasks)} tasks, over the {MAX_TASKS} limit")

    for index, task in enumerate(tasks):
        agent = capabilities.task_type_to_agent.get(task.task_type)
        if agent is None:
            raise PlanRejected(f"Task {index} has unknown task_type {task.task_type!r}")
        if task.assigned_to != agent:
            # A publish task routed to a content agent would run outside the
            # browser agent's constrained environment. Mismatches are never benign.
            raise PlanRejected(
                f"Task {index} ({task.task_type}) assigned to {task.assigned_to!r}, "
                f"but that task type belongs to {agent!r}"
            )

        for dep in task.depends_on_indices:
            if not 0 <= dep < len(tasks):
                raise PlanRejected(f"Task {index} depends on out-of-range index {dep}")
            if dep >= index:
                # Backwards-only dependencies make cycles structurally impossible,
                # which is cheaper to enforce than to detect.
                raise PlanRejected(
                    f"Task {index} depends on task {dep}, which is not earlier in the plan"
                )

    _assert_approval_gates_intact(tasks)
    _assert_reachable(tasks)

    log.info("plan.validated", extra={"task_count": len(tasks)})
    return tasks


def _assert_approval_gates_intact(tasks: list[PlannedTask]) -> None:
    """A plan may include gated tasks; it may not rename them to escape the gate.

    The gate keys off task_type, so the risk is a plan that achieves publishing
    through a task type the gate does not cover. Any task whose type merely
    resembles a gated action must be an actually-gated type.
    """
    suspicious = ("publish", "payment", "charge", "broadcast", "send_email", "go_live")
    for task in tasks:
        lowered = task.task_type.lower()
        if (
            any(word in lowered for word in suspicious)
            and task.task_type not in HUMAN_APPROVAL_REQUIRED
        ):
            raise PlanRejected(
                f"Task type {task.task_type!r} looks like an outward-facing action but is "
                "not in HUMAN_APPROVAL_REQUIRED; refusing to run it ungated"
            )


def _assert_reachable(tasks: list[PlannedTask]) -> None:
    """Every task must be reachable from a task with no dependencies.

    A plan whose tasks all depend on something is a plan that never starts; with
    backwards-only dependencies that means task 0 must be dependency-free.
    """
    if tasks[0].depends_on_indices:
        raise PlanRejected("The first task has dependencies, so nothing can ever start")


def to_launch_plan(tasks: list[PlannedTask]) -> list[tuple[str, str, list[int]]]:
    """Convert a validated plan into the orchestrator's internal plan format."""
    return [(task.task_type, task.assigned_to, list(task.depends_on_indices)) for task in tasks]
