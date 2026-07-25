"""Copywriting Agent.

Reads: market report, product draft, brand identity, and the funnel step being written.
Writes: CopyBlocks, plus winning headlines into long-term memory.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import CopyBlocks


class CopyAgent(BaseAgent):
    agent_name = "copy_agent"
    output_model = CopyBlocks

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        research = task_input.get("research_market", {})
        product = task_input.get("create_product", {})
        brand = task_input.get("create_brand", {})
        step_type = task_input.get("step_type", "optin")

        parts = [f"Write copy for a **{step_type}** page."]

        if audience := research.get("audience"):
            parts.append(f"Audience: {audience}")
        if pains := research.get("pain_points"):
            parts.append("Their pain points:\n" + "\n".join(f"- {p}" for p in pains))
        if product:
            parts.append(
                f"Product: {product.get('name', 'the offer')} — "
                f"{product.get('summary', 'a digital product')}"
            )
        if brand:
            parts.append(
                f"Brand: {brand.get('name', '')} — {brand.get('tagline', '')}. Match this voice."
            )
        if prior := task_input.get("winning_headlines"):
            parts.append(
                "Headlines that converted for a similar audience (for tone, not to copy):\n"
                + "\n".join(f"- {h}" for h in prior)
            )

        parts.append(
            "Return a JSON object with keys: headline, subheadline, bullets (array of "
            "3-5 benefit statements), cta (button text, under 5 words), body.\n"
            "Lead with the buyer's pain in their own language, not with the product. "
            "No superlatives you cannot support, no fake scarcity, no invented "
            "testimonials, numbers, or guarantees."
        )
        return "\n\n".join(parts)
