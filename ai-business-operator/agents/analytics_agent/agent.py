"""Analytics Agent.

Reads: systeme.io funnel stats and internal task/funnel data.
Writes: an AnalyticsReport — metrics, observations, recommendations, gaps.

Missing data windows are reported as gaps and never interpolated.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import AnalyticsReport


class AnalyticsAgent(BaseAgent):
    agent_name = "analytics_agent"
    output_model = AnalyticsReport

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        stats = task_input.get("stats", {})
        funnel = task_input.get("plan_funnel", {})
        window = task_input.get("window", "last 7 days")

        parts = [f"Analyse funnel performance over the {window}."]

        if funnel.get("name"):
            parts.append(f"Funnel: {funnel['name']}")
        if stats:
            parts.append(f"Raw metrics from systeme.io:\n{stats}")
        else:
            parts.append(
                "No metrics were returned for this window. Report this as a data gap; "
                "do not estimate what the numbers might have been."
            )
        if history := task_input.get("previous_snapshots"):
            parts.append(f"Previous snapshots for comparison:\n{history}")

        parts.append(
            "Return a JSON object: {metrics, observations, recommendations, "
            "data_gaps}.\n"
            "metrics is a flat object of numbers (visitors, optins, optin_rate, sales, "
            "revenue). Every observation must cite the metric it rests on. If a "
            "window has no data, list it in data_gaps — never interpolate, extrapolate, "
            "or fill a gap with a plausible number."
        )
        return "\n\n".join(parts)
