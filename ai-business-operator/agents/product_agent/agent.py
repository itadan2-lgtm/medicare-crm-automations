"""Product Creation Agent.

Reads: the market report and any user preferences on format and price.
Writes: a ProductDraft — outline plus drafted sections.

Long drafts are chunked per section so a single failure retries alone rather
than discarding the whole document.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import ProductDraft


class ProductAgent(BaseAgent):
    agent_name = "product_agent"
    output_model = ProductDraft

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        research = task_input.get("research_market", {})
        preferences = task_input.get("preferences", {})

        parts = ["Design a digital product for this market."]

        if audience := research.get("audience"):
            parts.append(f"Audience: {audience}")
        if pains := research.get("pain_points"):
            parts.append("Pains to solve:\n" + "\n".join(f"- {p}" for p in pains))
        if offers := research.get("existing_offers"):
            parts.append(
                "What they already buy (differentiate, do not clone):\n"
                + "\n".join(f"- {o}" for o in offers)
            )
        if price_range := research.get("price_range"):
            parts.append(f"Typical price range in this market: {price_range}")
        if preferences:
            parts.append(f"User preferences: {preferences}")
        if history := task_input.get("product_history"):
            parts.append(
                "Products this system built before (avoid repeating):\n"
                + "\n".join(f"- {h}" for h in history)
            )

        parts.append(
            "Return a JSON object: {name, product_type, summary, price_cents, "
            "sections: [{title, content}]}.\n"
            "product_type must be one of: ebook, course, template, checklist, toolkit. "
            "price_cents is an integer in cents. Write real content in each section — "
            "an outline with placeholder text is not a deliverable. Solve the stated "
            "pains specifically; do not pad."
        )
        return "\n\n".join(parts)
