"""Funnel Agent.

Reads: product, copy blocks, audience, price point.
Writes: a FunnelPlan — ordered steps mapped to copy.

Step types are validated against what systeme.io actually supports before anything
reaches the API, so an invented step type fails here rather than halfway through a build.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import FunnelPlan

# Mirrors the Literal in schemas.FunnelStepPlan. Kept here too so the prompt and the
# validator cannot drift apart silently.
SUPPORTED_STEP_TYPES = ("optin", "sales", "checkout", "upsell", "thankyou")


class FunnelAgent(BaseAgent):
    agent_name = "funnel_agent"
    output_model = FunnelPlan

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        research = task_input.get("research_market", {})
        product = task_input.get("create_product", {})
        copy = task_input.get("write_copy", {})

        parts = ["Design a systeme.io funnel for this offer."]

        if product:
            parts.append(
                f"Product: {product.get('name', 'the offer')} "
                f"({product.get('product_type', 'digital product')}), "
                f"price {product.get('price_cents', 0) / 100:.2f}"
            )
        if audience := research.get("audience"):
            parts.append(f"Audience: {audience}")
        if headline := copy.get("headline"):
            parts.append(f"Approved headline: {headline}")
        if patterns := task_input.get("funnel_patterns"):
            parts.append(
                "Funnel structures that worked in this niche before:\n"
                + "\n".join(f"- {p}" for p in patterns)
            )

        parts.append(
            "Return a JSON object: {name, steps: [{step_type, name, order, copy_ref}]}.\n"
            f"step_type must be one of: {', '.join(SUPPORTED_STEP_TYPES)}. "
            "These are the only types the integration supports — do not invent others "
            "(no webinar, no application, no survey steps).\n"
            "order is a zero-based integer and must be contiguous. Keep the funnel as "
            "short as the offer justifies; a low-priced product does not need an upsell "
            "chain."
        )
        return "\n\n".join(parts)

    def parse_output(self, raw: str):
        plan = super().parse_output(raw)
        assert isinstance(plan, FunnelPlan)

        orders = sorted(step.order for step in plan.steps)
        if orders != list(range(len(plan.steps))):
            from agents.base.llm import OutputParseError

            raise OutputParseError(f"Step orders must be contiguous from 0, got {orders}")
        return plan
