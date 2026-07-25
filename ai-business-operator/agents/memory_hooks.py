"""Connects agents to long-term memory around a task run.

Agents don't query memory themselves — the worker recalls relevant context before
building the prompt and persists what's worth keeping afterwards. Keeping it here
means an agent's `build_prompt` stays a pure function of its input, which is what
makes agents testable without a database.

What each agent gets back is keyed by its declared memory categories, so the
registry stays the single place that decides what an agent can see.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.registry import get_spec

log = logging.getLogger(__name__)

# Where recalled memory lands on the task input, per category. The key is what the
# agent's build_prompt looks for.
RECALL_KEYS: dict[str, str] = {
    "customer_pain": "prior_research",
    "niche": "prior_research",
    "competitor": "prior_research",
    "product_history": "product_history",
    "brand_style": "brand_styles",
    "headline": "winning_headlines",
    "cta": "winning_headlines",
    "copy_block": "winning_headlines",
    "funnel_pattern": "funnel_patterns",
    "email_performance": "email_performance",
    "automation_rule": "existing_rules",
    "experiment_result": "experiment_results",
    "analytics_snapshot": "previous_snapshots",
}


def recall_query(task_input: dict[str, Any]) -> str:
    """Build the similarity query from whatever context the task carries.

    Falls back through goal → niche → research audience, because early tasks have
    only a goal and later ones have richer upstream output.
    """
    for key in ("goal", "niche"):
        if value := task_input.get(key):
            return str(value)

    research = task_input.get("research_market") or {}
    for key in ("niche", "audience"):
        if value := research.get(key):
            return str(value)

    return " ".join(str(v) for v in task_input.values() if isinstance(v, str))[:500]


async def recall_context(
    agent_name: str, task_input: dict[str, Any], tools: dict[str, Any], *, top_k: int = 5
) -> dict[str, Any]:
    """Return a copy of `task_input` enriched with recalled memory.

    A memory failure is never fatal: an agent that works without prior context is
    less informed, not broken, and the alternative is blocking a run on a vector
    query.
    """
    reader = tools.get("memory_read")
    if reader is None:
        return task_input

    query = recall_query(task_input)
    if not query:
        return task_input

    enriched = dict(task_input)
    for category in sorted(get_spec(agent_name).memory_categories):
        target_key = RECALL_KEYS.get(category)
        if target_key is None:
            continue
        try:
            hits = await reader(query, category=category, top_k=top_k)
        except Exception as exc:  # noqa: BLE001 - memory is an enhancement, not a dependency
            log.warning(
                "memory.recall_failed",
                extra={"agent": agent_name, "category": category, "error": str(exc)[:200]},
            )
            continue

        if hits:
            enriched.setdefault(target_key, [])
            enriched[target_key] = [*enriched[target_key], *hits]

    return enriched


# What each agent persists after a successful run: (memory category, how to pull
# the values out of the agent's output).
PERSIST_RULES: dict[str, list[tuple[str, str]]] = {
    "research_agent": [("customer_pain", "pain_points")],
    "copy_agent": [("headline", "headline"), ("cta", "cta")],
    "branding_agent": [("brand_style", "palette")],
    "product_agent": [("product_history", "name")],
    "email_agent": [("email_performance", "sequence_name")],
    "funnel_agent": [("funnel_pattern", "name")],
}


async def persist_output(agent_name: str, output: dict[str, Any], tools: dict[str, Any]) -> int:
    """Write the durable parts of an output to memory. Returns the number stored.

    Only what is worth recalling later — a pain point, a headline, a funnel shape.
    Full drafts live in the relational tables; duplicating them into the vector
    store would bloat the index and drown the useful neighbours.
    """
    writer = tools.get("memory_write")
    if writer is None:
        return 0

    stored = 0
    for category, field in PERSIST_RULES.get(agent_name, []):
        value = output.get(field)
        if not value:
            continue

        values = value if isinstance(value, list) else [value]
        for item in values:
            text = str(item).strip()
            if not text:
                continue
            try:
                await writer(text, category=category)
                stored += 1
            except Exception as exc:  # noqa: BLE001 - a failed write must not fail the task
                log.warning(
                    "memory.write_failed",
                    extra={"agent": agent_name, "category": category, "error": str(exc)[:200]},
                )

    if stored:
        log.info("memory.persisted", extra={"agent": agent_name, "records": stored})
    return stored
