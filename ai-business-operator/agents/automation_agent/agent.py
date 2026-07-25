"""Automation Agent.

Reads: funnel steps, email sequence, contact lists.
Writes: an AutomationFlow — tags plus trigger/action rules for systeme.io.

Idempotent by tag name: re-running must not create duplicate tags.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import AutomationFlow


class AutomationAgent(BaseAgent):
    agent_name = "automation_agent"
    output_model = AutomationFlow

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        funnel = task_input.get("plan_funnel", {})
        emails = task_input.get("write_emails", {})
        existing_tags = task_input.get("existing_tags", [])

        parts = ["Define the automations wiring this funnel to its email sequences."]

        if steps := funnel.get("steps"):
            parts.append(
                "Funnel steps:\n"
                + "\n".join(
                    f"- {s.get('order')}: {s.get('step_type')} ({s.get('name')})" for s in steps
                )
            )
        if seq := emails.get("sequence_name"):
            count = len(emails.get("emails", []))
            parts.append(f"Email sequence: '{seq}' with {count} emails.")
        if existing_tags:
            parts.append(
                "Tags that already exist — reuse these names exactly rather than "
                "creating near-duplicates:\n" + "\n".join(f"- {t}" for t in existing_tags)
            )

        parts.append(
            "Return a JSON object: {tags, rules: [{trigger, action, target, "
            "delay_hours}]}.\n"
            "Tag names are lowercase-hyphenated and describe the contact's state "
            "('fitness-lead', 'purchased-starter'), not the campaign that set them. "
            "Keep the rule set small enough for a human to read and verify — this is "
            "the layer that decides who gets emailed, so obscurity is a real cost."
        )
        return "\n\n".join(parts)
