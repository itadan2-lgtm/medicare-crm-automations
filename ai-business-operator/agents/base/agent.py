"""BaseAgent — the contract every specialist implements.

Subclasses supply three things: a system prompt, a prompt built from the task input,
and an output model to validate against. Everything else — tool permission checks,
the one retry on a schema failure, error reporting — happens here.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.base.llm import LLM, OutputParseError, parse_as
from agents.registry import AgentSpec, get_spec

log = logging.getLogger(__name__)


class ToolNotPermitted(PermissionError):
    """An agent reached for a tool outside its declared set.

    This is a design error, not a runtime condition to handle. Widening the toolset
    to make it go away is the wrong fix — see CLAUDE.md rule 3.
    """


class BaseAgent(ABC):
    #: Set by each subclass; must match a key in the registry.
    agent_name: str

    #: Pydantic model the LLM response is validated against.
    output_model: type[BaseModel]

    def __init__(self, llm: LLM, tools: dict[str, Any] | None = None) -> None:
        self.spec: AgentSpec = get_spec(self.agent_name)
        self.llm = llm
        self._tools = tools or {}
        self.prompts = self._load_prompts()

    # --- Prompt plumbing ---------------------------------------------------

    def _load_prompts(self) -> dict[str, str]:
        path = Path(__file__).resolve().parent.parent / self.agent_name / "prompts.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def system_prompt(self) -> str:
        return self.prompts.get("system", f"You are the {self.agent_name}.")

    @abstractmethod
    def build_prompt(self, task_input: dict[str, Any]) -> str:
        """Turn a task's input into the user-turn prompt."""

    def parse_output(self, raw: str) -> BaseModel:
        """Validate the response. Override only for non-JSON outputs."""
        return parse_as(raw, self.output_model)

    # --- Tool access -------------------------------------------------------

    def attach_tools(self, tools: dict[str, Any]) -> None:
        """Replace the agent's toolset between tasks.

        Workers are long-lived but tools are per-task — memory and database handles
        are scoped to the project being worked on. Rebinding here keeps one agent
        instance from carrying another project's session.
        """
        self._tools = tools

    def use_tool(self, name: str) -> Any:
        if name not in self.spec.allowed_tools:
            raise ToolNotPermitted(
                f"{self.agent_name} may not use '{name}'. "
                f"Allowed: {', '.join(sorted(self.spec.allowed_tools))}"
            )
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is permitted for {self.agent_name} but was not provided")
        return self._tools[name]

    def may_use(self, name: str) -> bool:
        return name in self.spec.allowed_tools

    # --- Execution ---------------------------------------------------------

    async def run(self, task_input: dict[str, Any]) -> dict[str, Any]:
        """Work one task and return validated output.

        On a schema failure the model gets exactly one more attempt, with the
        validation error appended — models usually fix their own shape when shown
        what was wrong. A second failure is a real error and propagates.
        """
        prompt = self.build_prompt(task_input)
        raw = await self.llm.complete(system=self.system_prompt, prompt=prompt)

        try:
            return self.parse_output(raw).model_dump()
        except OutputParseError as first_error:
            log.warning(
                "agent.output_invalid",
                extra={"agent": self.agent_name, "error": str(first_error)[:300]},
            )
            retry_prompt = (
                f"{prompt}\n\n"
                f"Your previous response could not be parsed: {first_error}\n"
                f"Respond with a single valid JSON object matching the "
                f"{self.output_model.__name__} schema. No prose, no code fences."
            )
            raw = await self.llm.complete(system=self.system_prompt, prompt=retry_prompt)
            return self.parse_output(raw).model_dump()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.agent_name}>"
