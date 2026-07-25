"""Branding Agent.

Reads: market report, product theme.
Writes: a BrandIdentity — name, tagline, palette, logo prompt.

Image generation is non-blocking: if it fails the text identity still ships.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import BrandIdentity


class BrandingAgent(BaseAgent):
    agent_name = "branding_agent"
    output_model = BrandIdentity

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        research = task_input.get("research_market", {})
        product = task_input.get("create_product", {})

        parts = ["Create a brand identity for this business."]

        if audience := research.get("audience"):
            parts.append(f"Audience: {audience}")
        if product:
            parts.append(f"Product: {product.get('name', '')} — {product.get('summary', '')}")
        if angles := research.get("angles"):
            parts.append(
                "Positioning angles under consideration:\n" + "\n".join(f"- {a}" for a in angles)
            )
        if styles := task_input.get("brand_styles"):
            parts.append(
                "Palettes and naming patterns used before (for consistency, not reuse):\n"
                + "\n".join(f"- {s}" for s in styles)
            )

        parts.append(
            "Return a JSON object: {name, tagline, palette, logo_prompt}.\n"
            "palette is an array of 3-5 hex colours with sufficient contrast for body "
            "text on the lightest one. The name must be pronounceable, spellable after "
            "hearing it once, and not a real existing company or trademark you know of. "
            "logo_prompt describes an original mark — never reference a living artist's "
            "style or an existing brand's logo."
        )
        return "\n\n".join(parts)
