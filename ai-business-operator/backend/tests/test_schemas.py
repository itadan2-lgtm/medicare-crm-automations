"""The task/event contract and the agent output schemas.

These are the shapes every other component depends on, so they get tested without
a database or a network.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas import (
    Event,
    EventType,
    FunnelPlan,
    MarketReport,
    TaskCreate,
    TaskResult,
    TaskStatus,
)


def test_task_status_terminal_states() -> None:
    assert TaskStatus.DONE.is_terminal
    assert TaskStatus.BLOCKED.is_terminal
    assert TaskStatus.CANCELLED.is_terminal
    assert not TaskStatus.PENDING.is_terminal
    assert not TaskStatus.AWAITING_APPROVAL.is_terminal


def test_task_create_defaults() -> None:
    task = TaskCreate(project_id=7, task_type="write_copy", assigned_to="copy_agent")
    assert task.input == {}
    assert task.depends_on == []


def test_event_signable_excludes_signature() -> None:
    event = Event(
        event=EventType.TASK_COMPLETED,
        project_id=7,
        task_id=1024,
        agent="funnel_agent",
        result={"funnel_id": 55},
        timestamp=datetime.now(UTC),
        signature="hmac-sha256:deadbeef",
    )
    assert "signature" not in event.signable()
    assert "funnel_agent" in event.signable()


def test_market_report_requires_pain_points() -> None:
    with pytest.raises(ValidationError):
        MarketReport(niche="fitness", audience="busy parents")  # type: ignore[call-arg]


def test_funnel_plan_rejects_unsupported_step_type() -> None:
    # The funnel agent validates against this before anything reaches systeme.io —
    # an invented step type must fail here, not halfway through a build.
    with pytest.raises(ValidationError):
        FunnelPlan.model_validate(
            {"name": "Launch", "steps": [{"step_type": "webinar", "name": "Live", "order": 0}]}
        )


def test_funnel_plan_accepts_supported_steps() -> None:
    plan = FunnelPlan.model_validate(
        {
            "name": "Home Fitness Launch",
            "steps": [
                {"step_type": "optin", "name": "Free guide", "order": 0},
                {"step_type": "sales", "name": "Main offer", "order": 1},
                {"step_type": "thankyou", "name": "Thanks", "order": 2},
            ],
        }
    )
    assert [s.step_type for s in plan.steps] == ["optin", "sales", "thankyou"]


def test_task_result_failure_carries_error() -> None:
    result = TaskResult(task_id=1, agent="copy_agent", success=False, error="LLM timeout")
    assert not result.success
    assert result.error == "LLM timeout"
    assert result.output == {}
