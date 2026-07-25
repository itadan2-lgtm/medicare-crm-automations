"""Plan validation.

A plan is a set of instructions the system executes autonomously, so it is treated
as adversarial input. These tests pin what must be rejected.
"""

from __future__ import annotations

import pytest

from app.schemas import PlannedTask, ProjectPlan
from app.services.planning import (
    MAX_TASKS,
    AgentCapabilities,
    PlanRejected,
    to_launch_plan,
    validate_plan,
)

CAPS = AgentCapabilities(
    task_type_to_agent={
        "research_market": "research_agent",
        "create_product": "product_agent",
        "write_copy": "copy_agent",
        "publish_funnel": "browser_agent",
    }
)


def plan_of(*tasks: tuple[str, str, list[int]]) -> ProjectPlan:
    return ProjectPlan(
        summary="test plan",
        tasks=[PlannedTask(task_type=t, assigned_to=a, depends_on_indices=d) for t, a, d in tasks],
    )


def test_accepts_a_well_formed_plan() -> None:
    plan = plan_of(
        ("research_market", "research_agent", []),
        ("create_product", "product_agent", [0]),
        ("write_copy", "copy_agent", [0, 1]),
    )
    tasks = validate_plan(plan, CAPS)
    assert len(tasks) == 3
    assert to_launch_plan(tasks)[2] == ("write_copy", "copy_agent", [0, 1])


def test_rejects_empty_plan() -> None:
    with pytest.raises(PlanRejected, match="no tasks"):
        validate_plan(ProjectPlan(summary="", tasks=[]), CAPS)


def test_rejects_unknown_task_type() -> None:
    plan = plan_of(("hack_the_gibson", "research_agent", []))
    with pytest.raises(PlanRejected, match="unknown task_type"):
        validate_plan(plan, CAPS)


def test_rejects_task_routed_to_the_wrong_agent() -> None:
    """Routing a publish task to a content agent would run it outside the browser
    agent's constrained environment."""
    plan = plan_of(("publish_funnel", "copy_agent", []))
    with pytest.raises(PlanRejected, match="belongs to"):
        validate_plan(plan, CAPS)


def test_rejects_forward_dependency() -> None:
    plan = plan_of(
        ("research_market", "research_agent", []),
        ("create_product", "product_agent", [2]),
        ("write_copy", "copy_agent", []),
    )
    with pytest.raises(PlanRejected, match="not earlier in the plan"):
        validate_plan(plan, CAPS)


def test_rejects_self_dependency() -> None:
    plan = plan_of(("research_market", "research_agent", [0]))
    with pytest.raises(PlanRejected):
        validate_plan(plan, CAPS)


def test_rejects_out_of_range_dependency() -> None:
    plan = plan_of(
        ("research_market", "research_agent", []),
        ("create_product", "product_agent", [99]),
    )
    with pytest.raises(PlanRejected, match="out-of-range"):
        validate_plan(plan, CAPS)


def test_rejects_plan_that_can_never_start() -> None:
    plan = ProjectPlan(
        summary="",
        tasks=[
            PlannedTask(
                task_type="research_market", assigned_to="research_agent", depends_on_indices=[0]
            )
        ],
    )
    with pytest.raises(PlanRejected):
        validate_plan(plan, CAPS)


def test_rejects_oversized_plan() -> None:
    plan = plan_of(*[("research_market", "research_agent", [])] * (MAX_TASKS + 1))
    with pytest.raises(PlanRejected, match="over the"):
        validate_plan(plan, CAPS)


def test_rejects_ungated_outward_facing_task_type() -> None:
    """The approval gate keys off task_type. A plan must not reach the outside world
    through a type the gate does not cover."""
    caps = AgentCapabilities(
        task_type_to_agent={"publish_pages_now": "browser_agent"},
    )
    plan = plan_of(("publish_pages_now", "browser_agent", []))
    with pytest.raises(PlanRejected, match="HUMAN_APPROVAL_REQUIRED"):
        validate_plan(plan, caps)


def test_gated_task_type_is_allowed() -> None:
    plan = plan_of(("publish_funnel", "browser_agent", []))
    assert len(validate_plan(plan, CAPS)) == 1


def test_capabilities_from_registry_covers_the_real_agents() -> None:
    caps = AgentCapabilities.from_registry()
    assert caps.task_type_to_agent["write_copy"] == "copy_agent"
    assert caps.task_type_to_agent["publish_funnel"] == "browser_agent"


def test_the_fixed_launch_plan_passes_its_own_validator() -> None:
    """The fallback must always be valid — it is what a rejected plan falls back to."""
    from app.services.orchestrator import LAUNCH_PLAN

    plan = plan_of(*LAUNCH_PLAN)
    assert len(validate_plan(plan, AgentCapabilities.from_registry())) == len(LAUNCH_PLAN)
