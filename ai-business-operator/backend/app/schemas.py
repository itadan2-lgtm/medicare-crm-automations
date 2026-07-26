"""Wire-format schemas: the canonical task and event contract.

If a field changes here, update `docs/architecture.md` in the same commit — agents,
the orchestrator, the frontend, and the event bus all read from this module.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    WORKING = "working"
    DONE = "done"
    ERROR = "error"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {TaskStatus.DONE, TaskStatus.BLOCKED, TaskStatus.CANCELLED}


class EventType(StrEnum):
    TASK_CREATED = "task_created"
    TASK_CLAIMED = "task_claimed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    MARKET_RESEARCH_DONE = "market_research_done"
    PRODUCT_DRAFTED = "product_drafted"
    BRANDING_DONE = "branding_done"
    COPY_DONE = "copy_done"
    FUNNEL_PLANNED = "funnel_planned"
    EMAILS_DRAFTED = "emails_drafted"
    AUTOMATIONS_READY = "automations_ready"
    PAGES_BUILT = "pages_built"
    ANALYTICS_READY = "analytics_ready"
    OPTIMIZATION_PROPOSED = "optimization_proposed"


# --- Tasks -----------------------------------------------------------------


class TaskBase(BaseModel):
    project_id: int
    task_type: str
    assigned_to: str
    input: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: TaskStatus
    output: dict[str, Any] | None = None
    attempts: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TaskResult(BaseModel):
    """What an agent hands back after working a task."""

    task_id: int
    agent: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    emits: EventType | None = None
    retryable: bool = Field(
        default=True,
        description=(
            "False for failures a retry cannot fix — an expired key, exhausted "
            "credits, revoked permission. These block immediately rather than "
            "spending every task's retry budget on a condition only a human clears."
        ),
    )


# --- Events ----------------------------------------------------------------


class Event(BaseModel):
    """Message published on Redis pub/sub.

    `signature` is an HMAC-SHA256 over the canonical JSON of every other field,
    keyed by JWT_SECRET. Subscribers drop unsigned or mis-signed events — this is
    the trust boundary between workers.
    """

    event: EventType
    project_id: int
    task_id: int | None = None
    agent: str
    result: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    signature: str | None = None

    def signable(self) -> str:
        """Canonical JSON of the payload, excluding the signature itself."""
        return self.model_dump_json(exclude={"signature"})


# --- Users and auth --------------------------------------------------------


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, description="Minimum 12 characters.")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: EmailStr
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - scheme name, not a credential


# --- Projects --------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    goal: str = Field(description="One line, e.g. 'Launch a home-fitness ebook business'.")
    niche: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: int
    user_id: int
    name: str
    goal: str
    niche: str | None
    status: str
    created_at: datetime


# --- Agent output contracts -------------------------------------------------
# Agents must produce these shapes. Anything else is a parse failure and is
# retried with the validation error attached — never acted on.


class MarketReport(BaseModel):
    niche: str
    audience: str
    pain_points: list[str]
    existing_offers: list[str] = Field(default_factory=list)
    price_range: str | None = None
    angles: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class BrandIdentity(BaseModel):
    name: str
    tagline: str
    palette: list[str] = Field(default_factory=list, description="Hex colours.")
    logo_prompt: str | None = None


class CopyBlocks(BaseModel):
    headline: str
    subheadline: str | None = None
    bullets: list[str] = Field(default_factory=list)
    cta: str
    body: str | None = None


class FunnelStepPlan(BaseModel):
    step_type: Literal["optin", "sales", "checkout", "upsell", "thankyou"]
    name: str
    order: int
    copy_ref: str | None = Field(
        default=None, description="Key into the copy agent's output for this step."
    )


class FunnelPlan(BaseModel):
    name: str
    steps: list[FunnelStepPlan]


class EmailDraft(BaseModel):
    subject: str
    body: str
    send_delay_hours: int = 0
    position: int = 0


class EmailSequence(BaseModel):
    sequence_name: str
    emails: list[EmailDraft]


class OptimizationSuggestion(BaseModel):
    target: str = Field(description="What to change, e.g. 'optin.headline'.")
    current_value: str | None = None
    proposed_value: str
    rationale: str
    expected_lift: str | None = None


class OptimizationPlan(BaseModel):
    suggestions: list[OptimizationSuggestion] = Field(default_factory=list)
    sample_size: int | None = None
    note: str | None = Field(
        default=None,
        description="Set when the sample is too small to justify any change.",
    )


class ProductDraft(BaseModel):
    name: str
    product_type: Literal["ebook", "course", "template", "checklist", "toolkit"]
    summary: str
    price_cents: int = Field(ge=0)
    sections: list[dict[str, Any]] = Field(
        default_factory=list, description="Ordered {title, content} blocks."
    )


class PlannedTask(BaseModel):
    task_type: str
    assigned_to: str
    depends_on_indices: list[int] = Field(
        default_factory=list, description="Indices into this plan's own task list."
    )


class ProjectPlan(BaseModel):
    summary: str
    tasks: list[PlannedTask]


class AutomationRule(BaseModel):
    trigger: str = Field(description="e.g. 'optin_submitted' or 'tag_applied:fitness-lead'.")
    action: str = Field(description="e.g. 'apply_tag' or 'start_sequence'.")
    target: str
    delay_hours: int = 0


class AutomationFlow(BaseModel):
    tags: list[str] = Field(default_factory=list)
    rules: list[AutomationRule] = Field(default_factory=list)


class AnalyticsReport(BaseModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    data_gaps: list[str] = Field(
        default_factory=list, description="Windows with no data. Never interpolated."
    )


class BrowserResult(BaseModel):
    steps_executed: list[str] = Field(default_factory=list)
    resource_ids: dict[str, str] = Field(default_factory=dict)
    screenshots: list[str] = Field(default_factory=list)
    succeeded: bool = True
