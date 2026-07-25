"""Market Research Agent.

Reads: niche keyword and any industry signals on the task input.
Writes: a MarketReport, plus customer-pain records into long-term memory.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.base.agent import BaseAgent
from agents.base.llm import wrap_untrusted
from app.schemas import MarketReport

log = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    agent_name = "research_agent"
    output_model = MarketReport

    def build_prompt(self, task_input: dict[str, Any]) -> str:
        goal = task_input.get("goal", "")
        niche = task_input.get("niche") or goal
        signals = task_input.get("signals", [])

        parts = [
            f"Business goal: {goal}",
            f"Niche to research: {niche}",
        ]

        if prior := task_input.get("prior_research"):
            parts.append(
                "Previously learned about this niche (from memory — reuse, do not repeat):\n"
                + "\n".join(f"- {item}" for item in prior)
            )

        if signals:
            # Search results are third-party text. Fence them so the model treats
            # them as data rather than as instructions.
            joined = "\n\n".join(str(s) for s in signals)
            parts.append(wrap_untrusted(joined, source="web_search"))

        parts.append(
            "Produce a market report as a JSON object with keys: niche, audience, "
            "pain_points (array of specific, concrete pains in the buyer's own words), "
            "existing_offers (array), price_range (string or null), angles (array of "
            "positioning angles), confidence ('low' | 'medium' | 'high').\n"
            "Set confidence to 'low' if you are working from general knowledge rather "
            "than the supplied signals. Do not invent competitor names, statistics, or "
            "citations — an empty array is a better answer than a fabricated one."
        )
        return "\n\n".join(parts)

    async def gather_signals(self, niche: str) -> list[str]:
        """Pull fresh search results for the niche.

        TODO(phase-4): wire to the real search tool. Until then the agent runs on
        model knowledge and reports confidence 'low', which is honest rather than
        quietly wrong.
        """
        if not self.may_use("web_search"):
            return []
        search = self.use_tool("web_search")
        return await search(niche)
