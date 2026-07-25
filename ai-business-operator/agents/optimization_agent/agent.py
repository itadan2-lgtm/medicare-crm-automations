"""Optimization Agent.

Reads: analytics data, conversion rates, prior experiment results.
Writes: an OptimizationPlan — ranked, testable changes.

Refuses to propose changes below MIN_SAMPLE_SIZE and says so, rather than
reading noise as signal. Applying a suggestion is a gated task type.
"""

from __future__ import annotations

from typing import Any

from agents.base.agent import BaseAgent
from app.schemas import OptimizationPlan

# Below this many visitors, differences in conversion rate are noise.
MIN_SAMPLE_SIZE = 100


class OptimizationAgent(BaseAgent):
    agent_name = "optimization_agent"
    output_model = OptimizationPlan

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        analytics = task_input.get("collect_analytics", {})
        copy = task_input.get("write_copy", {})
        sample = int(analytics.get("metrics", {}).get("visitors", 0))

        parts = ["Propose improvements to this funnel."]

        if metrics := analytics.get("metrics"):
            parts.append(f"Current metrics:\n{metrics}")
        if observations := analytics.get("observations"):
            parts.append("Analyst observations:\n" + "\n".join(f"- {o}" for o in observations))
        if copy:
            parts.append(f"Current headline: {copy.get('headline', 'unknown')}")
        if failures := task_input.get("experiment_results"):
            parts.append(
                "Changes already tested — do not re-propose a loser:\n"
                + "\n".join(f"- {f}" for f in failures)
            )

        parts.append(
            f"Observed sample size: {sample} visitors. MIN_SAMPLE_SIZE is {MIN_SAMPLE_SIZE}."
        )
        parts.append(
            "Return a JSON object: {suggestions: [{target, current_value, "
            "proposed_value, rationale, expected_lift}], sample_size, note}.\n"
            "If the sample is below MIN_SAMPLE_SIZE, return an empty suggestions array "
            "and explain in `note` that there is not enough data yet. Do not read noise "
            "as signal. Rank suggestions by expected impact, one variable per "
            "suggestion so the result is attributable."
        )
        return "\n\n".join(parts)
