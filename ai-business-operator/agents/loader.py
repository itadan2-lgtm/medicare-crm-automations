"""Resolve an agent name to its implementation.

Agents are loaded by convention: `agents/<name>/agent.py` exposing a single
`BaseAgent` subclass. Importing lazily keeps a worker from pulling in every other
agent's dependencies — the browser agent has no business importing an LLM client.
"""

from __future__ import annotations

import importlib
import inspect

from agents.base.agent import BaseAgent
from agents.base.llm import LLM
from agents.registry import get_spec


def load_agent(agent_name: str, llm: LLM, tools: dict | None = None) -> BaseAgent:
    get_spec(agent_name)  # fail fast on an unknown name

    try:
        module = importlib.import_module(f"agents.{agent_name}.agent")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(f"No implementation at agents/{agent_name}/agent.py") from exc

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BaseAgent)
            and obj is not BaseAgent
            and getattr(obj, "agent_name", None) == agent_name
        ):
            return obj(llm, tools)

    raise TypeError(
        f"agents/{agent_name}/agent.py defines no BaseAgent with agent_name={agent_name!r}"
    )
