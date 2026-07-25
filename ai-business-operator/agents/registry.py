"""The enforced copy of the agent contract in AGENTS.md.

`BaseAgent.use_tool()` checks against this. If you change a row in AGENTS.md, change
it here in the same commit — the doc is the specification, this is the enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    allowed_tools: frozenset[str]
    task_types: frozenset[str]
    memory_categories: frozenset[str] = field(default_factory=frozenset)


# The complete tool vocabulary. A tool outside this set is a typo.
TOOLS = frozenset(
    {
        "llm",
        "web_search",
        "image_gen",
        "db_read",
        "db_write",
        "memory_read",
        "memory_write",
        "task_queue",
        "systemeio_mcp",
        "systemeio_api",
        "playwright",
        "metrics",
        "file_write",
    }
)


REGISTRY: dict[str, AgentSpec] = {
    "ceo_agent": AgentSpec(
        name="ceo_agent",
        description="Orchestrator: plans the task graph, retries failures, releases approvals.",
        allowed_tools=frozenset({"task_queue", "db_read", "db_write", "llm"}),
        task_types=frozenset({"plan_project", "replan_project"}),
    ),
    "research_agent": AgentSpec(
        name="research_agent",
        description="Analyses the market, audience and competitors for a niche.",
        allowed_tools=frozenset({"web_search", "llm", "memory_read", "memory_write"}),
        task_types=frozenset({"research_market"}),
        memory_categories=frozenset({"customer_pain", "niche", "competitor"}),
    ),
    "product_agent": AgentSpec(
        name="product_agent",
        description="Designs and drafts the digital product.",
        allowed_tools=frozenset({"llm", "memory_read", "memory_write", "file_write"}),
        task_types=frozenset({"create_product"}),
        memory_categories=frozenset({"product_history"}),
    ),
    "branding_agent": AgentSpec(
        name="branding_agent",
        description="Generates brand identity: name, palette, logo prompt.",
        allowed_tools=frozenset({"llm", "image_gen", "memory_read", "memory_write"}),
        task_types=frozenset({"create_brand"}),
        memory_categories=frozenset({"brand_style"}),
    ),
    "copy_agent": AgentSpec(
        name="copy_agent",
        description="Writes marketing copy for landing and sales pages.",
        allowed_tools=frozenset({"llm", "memory_read", "memory_write"}),
        task_types=frozenset({"write_copy", "rewrite_headline"}),
        memory_categories=frozenset({"headline", "cta", "copy_block"}),
    ),
    "funnel_agent": AgentSpec(
        name="funnel_agent",
        description="Designs the funnel structure and step order.",
        allowed_tools=frozenset({"llm", "db_read", "memory_read", "memory_write"}),
        task_types=frozenset({"plan_funnel"}),
        memory_categories=frozenset({"funnel_pattern"}),
    ),
    "email_agent": AgentSpec(
        name="email_agent",
        description="Writes welcome and follow-up email sequences.",
        allowed_tools=frozenset({"llm", "memory_read", "memory_write"}),
        task_types=frozenset({"write_emails"}),
        memory_categories=frozenset({"email_performance"}),
    ),
    "automation_agent": AgentSpec(
        name="automation_agent",
        description="Defines tags, triggers and delays wiring the funnel to the emails.",
        allowed_tools=frozenset({"systemeio_mcp", "db_read", "llm"}),
        task_types=frozenset({"configure_automations"}),
        memory_categories=frozenset({"automation_rule"}),
    ),
    "browser_agent": AgentSpec(
        name="browser_agent",
        # Deliberately the narrowest toolset: it is the most exposed process, so it
        # holds no LLM key, no database access and no memory.
        description="Drives the systeme.io UI via Playwright for what the API can't do.",
        allowed_tools=frozenset({"playwright", "systemeio_api"}),
        task_types=frozenset({"build_pages", "publish_funnel", "publish_page"}),
    ),
    "analytics_agent": AgentSpec(
        name="analytics_agent",
        description="Monitors funnel results and computes metrics.",
        allowed_tools=frozenset({"systemeio_api", "db_read", "metrics", "llm"}),
        task_types=frozenset({"collect_analytics"}),
        memory_categories=frozenset({"analytics_snapshot"}),
    ),
    "optimization_agent": AgentSpec(
        name="optimization_agent",
        description="Proposes A/B tests and funnel tweaks from analytics data.",
        allowed_tools=frozenset({"llm", "db_read", "memory_read", "memory_write"}),
        task_types=frozenset({"propose_optimizations"}),
        memory_categories=frozenset({"experiment_result"}),
    ),
}


def get_spec(agent_name: str) -> AgentSpec:
    try:
        return REGISTRY[agent_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown agent '{agent_name}'. Known agents: {', '.join(sorted(REGISTRY))}"
        ) from exc


def agent_for_task_type(task_type: str) -> str:
    for spec in REGISTRY.values():
        if task_type in spec.task_types:
            return spec.name
    raise KeyError(f"No agent handles task type '{task_type}'")
