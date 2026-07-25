"""Orchestrator planning rules and the human-approval gate.

The dependency-graph and claim-query behaviour needs a live Postgres and is covered
by the integration suite (Phase 3). These tests pin the logic that can be checked
without one — which includes the safety rail that matters most.
"""

from __future__ import annotations

from app.config import HUMAN_APPROVAL_REQUIRED, Settings
from app.services.orchestrator import COMPLETION_EVENTS, LAUNCH_PLAN, Orchestrator


def orchestrator_with(**overrides: object) -> Orchestrator:
    orch = Orchestrator.__new__(Orchestrator)  # no session needed for these checks
    orch.settings = Settings(**overrides)  # type: ignore[arg-type]
    orch.bus = None
    return orch


def test_launch_plan_dependencies_point_backwards() -> None:
    """A task may only depend on one earlier in the plan — otherwise the graph
    would contain a cycle and nothing would ever become claimable."""
    for index, (task_type, _agent, deps) in enumerate(LAUNCH_PLAN):
        for dep in deps:
            assert dep < index, f"{task_type} depends on a later task ({dep} >= {index})"


def test_launch_plan_agents_are_known() -> None:
    known = {
        "research_agent",
        "product_agent",
        "branding_agent",
        "copy_agent",
        "funnel_agent",
        "email_agent",
        "automation_agent",
        "browser_agent",
        "analytics_agent",
        "optimization_agent",
    }
    for _task_type, agent, _deps in LAUNCH_PLAN:
        assert agent in known, f"{agent} is not in the agent registry"


def test_launch_plan_starts_with_research() -> None:
    task_type, agent, deps = LAUNCH_PLAN[0]
    assert (task_type, agent, deps) == ("research_market", "research_agent", [])


def test_publishing_requires_approval() -> None:
    orch = orchestrator_with(require_human_approval=True)
    assert orch.requires_approval("publish_funnel")
    assert orch.requires_approval("create_payment")
    assert not orch.requires_approval("write_copy")


def test_approval_gate_can_be_disabled_only_by_config() -> None:
    orch = orchestrator_with(require_human_approval=False)
    assert not orch.requires_approval("publish_funnel")


def test_launch_plan_publishes_only_behind_the_gate() -> None:
    """Every task in the plan that reaches the outside world irreversibly must be
    a gated type. If someone adds one that isn't, this fails."""
    outward = {"publish_funnel", "publish_page", "send_broadcast", "create_payment"}
    for task_type, _agent, _deps in LAUNCH_PLAN:
        if task_type in outward:
            assert task_type in HUMAN_APPROVAL_REQUIRED


def test_completion_events_cover_planned_tasks() -> None:
    for task_type, _agent, _deps in LAUNCH_PLAN:
        if task_type == "publish_funnel":
            continue  # publishing emits the generic task_completed
        assert task_type in COMPLETION_EVENTS, f"{task_type} has no completion event"
