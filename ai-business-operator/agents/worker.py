"""Agent worker loop.

Claims a task, runs the agent, reports the result. One process per agent type; run
several of the same type freely — claiming uses SKIP LOCKED, so no two workers get
the same row.

    python -m agents.worker --agent research_agent
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.base.llm import ClaudeLLM
from agents.loader import load_agent
from agents.memory_hooks import persist_output, recall_context
from agents.tools import build_toolset, release_toolset
from app.config import get_settings
from app.database import dispose_engine, get_sessionmaker
from app.logging_config import configure_logging
from app.schemas import TaskResult
from app.services.events import EventBus
from app.services.orchestrator import Orchestrator

log = logging.getLogger(__name__)


class Worker:
    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.worker_id = f"{agent_name}-{uuid.uuid4().hex[:8]}"
        self.settings = get_settings()
        self._stop = asyncio.Event()
        self._recent_errors = 0

    def request_stop(self) -> None:
        log.info("worker.stopping", extra={"worker_id": self.worker_id})
        self._stop.set()

    async def run(self) -> None:
        llm = ClaudeLLM(self.settings.anthropic_api_key, self.settings.anthropic_model)
        agent = load_agent(self.agent_name, llm)
        bus = EventBus.from_env()
        sessionmaker = get_sessionmaker()

        log.info(
            "worker.started",
            extra={"worker_id": self.worker_id, "agent": self.agent_name},
        )

        try:
            while not self._stop.is_set():
                worked = await self._tick(sessionmaker, agent, bus)
                if not worked:
                    # Nothing claimable; wait rather than hammering the database.
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(
                            self._stop.wait(), timeout=self.settings.worker_poll_interval_seconds
                        )
        finally:
            await bus.aclose()
            await dispose_engine()
            log.info("worker.stopped", extra={"worker_id": self.worker_id})

    async def _tick(self, sessionmaker, agent, bus: EventBus) -> bool:
        async with sessionmaker() as session:
            orchestrator = Orchestrator(session, bus)
            task = await orchestrator.claim_next_task(self.agent_name, self.worker_id)
            if task is None:
                await session.commit()
                return False

            task_id = task.task_id
            project_id = task.project_id
            task_input = dict(task.input)
            task_input.setdefault("task_type", task.task_type)
            await session.commit()

        # Tools and memory share one session for the duration of the run. It is
        # separate from the claim transaction so a long agent call is not holding a
        # row lock while the model thinks.
        async with sessionmaker() as tool_session:
            tools = await build_toolset(
                self.agent_name,
                project_id=project_id,
                session=tool_session,
                settings=self.settings,
            )
            agent.attach_tools(tools)

            try:
                enriched = await recall_context(self.agent_name, task_input, tools)
                output = await agent.run(enriched)
                await persist_output(self.agent_name, output, tools)
                await tool_session.commit()

                result = TaskResult(
                    task_id=task_id, agent=self.agent_name, success=True, output=output
                )
                self._recent_errors = 0
            except Exception as exc:
                await tool_session.rollback()
                log.exception("agent.failed", extra={"task_id": task_id, "agent": self.agent_name})
                result = TaskResult(
                    task_id=task_id,
                    agent=self.agent_name,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}"[:1000],
                )
                self._recent_errors += 1
            finally:
                await release_toolset(tools)

        async with sessionmaker() as session:
            await Orchestrator(session, bus).complete_task(result)
            await session.commit()

        # Circuit breaker: stop burning tokens and rate-limit budget on a
        # persistently failing agent. The orchestrator surfaces the blocked tasks.
        if self._recent_errors >= self.settings.agent_error_threshold:
            log.error(
                "worker.circuit_open",
                extra={"agent": self.agent_name, "consecutive_errors": self._recent_errors},
            )
            self.request_stop()

        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an AI Business Operator agent worker.")
    parser.add_argument("--agent", required=True, help="Agent name, e.g. research_agent")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    worker = Worker(args.agent)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, worker.request_stop)

    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
