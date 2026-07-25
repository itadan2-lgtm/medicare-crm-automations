"""Email Agent.

Reads: product info, funnel plan, audience, brand voice.
Writes: an EmailSequence — subject, body and send delay per email.

A partial sequence is still persisted and flagged rather than discarded.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import EmailSequence


class EmailAgent(BaseAgent):
    agent_name = "email_agent"
    output_model = EmailSequence

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        research = task_input.get("research_market", {})
        product = task_input.get("create_product", {})
        funnel = task_input.get("plan_funnel", {})
        sequence = task_input.get("sequence_name", "welcome")

        parts = [f"Write the '{sequence}' email sequence."]

        if audience := research.get("audience"):
            parts.append(f"Audience: {audience}")
        if pains := research.get("pain_points"):
            parts.append("Their pains:\n" + "\n".join(f"- {p}" for p in pains))
        if product:
            parts.append(f"Product: {product.get('name', '')} — {product.get('summary', '')}")
        if steps := funnel.get("steps"):
            parts.append(
                "Funnel steps the sequence supports: "
                + ", ".join(str(s.get("step_type")) for s in steps)
            )
        if performance := task_input.get("email_performance"):
            parts.append(
                "Subject patterns that performed well before:\n"
                + "\n".join(f"- {p}" for p in performance)
            )

        parts.append(
            "Return a JSON object: {sequence_name, emails: [{subject, body, "
            "send_delay_hours, position}]}.\n"
            "4-6 emails. position is zero-based and contiguous; send_delay_hours is "
            "measured from the previous email (0 for the first). Subjects under 60 "
            "characters, no clickbait, no fake 'Re:' or 'Fwd:' prefixes. Each email "
            "must deliver something useful on its own — do not write five emails that "
            "only tease the next one. No invented urgency or expiring discounts unless "
            "one was actually configured."
        )
        return "\n\n".join(parts)
