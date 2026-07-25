"""Dispatches a browser task to the right Playwright script.

Failure policy: screenshot, one retry, then report to the orchestrator. Errors are
never swallowed — a half-built funnel that reports success is worse than a clear
failure, because nobody goes looking for it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.schemas import BrowserResult

log = logging.getLogger(__name__)


async def execute_task(task_input: dict[str, Any]) -> BrowserResult:
    task_type = task_input.get("task_type", "build_pages")

    handlers = {
        "build_pages": build_pages,
        "publish_funnel": publish_funnel,
        "publish_page": publish_funnel,
    }
    handler = handlers.get(task_type)
    if handler is None:
        raise ValueError(f"browser_agent does not handle task type {task_type!r}")

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            return await handler(task_input)
        except Exception as exc:  # noqa: BLE001 - retried once, then reported upward
            last_error = exc
            log.warning(
                "browser.attempt_failed",
                extra={"task_type": task_type, "attempt": attempt, "error": str(exc)[:200]},
            )
            if attempt == 0:
                await asyncio.sleep(2)

    assert last_error is not None
    raise last_error


async def build_pages(task_input: dict[str, Any]) -> BrowserResult:
    """Build the funnel's pages: steps, templates, copy, brand colours."""
    from browser_agent.playwright_scripts import base, create_funnel, fill_page

    plan = task_input.get("plan_funnel", {})
    copy_blocks = task_input.get("write_copy", {})
    brand = task_input.get("create_brand", {})

    funnel_name = plan.get("name")
    if not funnel_name:
        raise ValueError("build_pages requires a funnel plan with a name")

    executed: list[str] = []
    resource_ids: dict[str, str] = {}
    screenshots: list[str] = []

    async with base.browser_session() as (_browser, _context, page):
        try:
            await base.login(
                page,
                os.environ["SYSTEMEIO_LOGIN_EMAIL"],
                os.environ["SYSTEMEIO_LOGIN_PASSWORD"],
            )
            executed.append("login")

            await create_funnel.open_funnel(page, funnel_name)
            executed.append(f"open_funnel:{funnel_name}")

            for step in sorted(plan.get("steps", []), key=lambda s: s.get("order", 0)):
                step_type = step["step_type"]
                step_id = await create_funnel.add_step(page, step_type, step.get("name", step_type))
                resource_ids[f"step_{step['order']}"] = step_id
                executed.append(f"add_step:{step_type}")

                written = await fill_page.apply_copy(page, copy_blocks)
                executed.append(f"apply_copy:{','.join(written) or 'none'}")

                if palette := brand.get("palette"):
                    await fill_page.apply_palette(page, palette)
                    executed.append("apply_palette")

                await fill_page.save(page)
                executed.append("save")

        except Exception:
            screenshots.append(await base.capture_failure(page, "build_pages"))
            raise

    return BrowserResult(
        steps_executed=executed,
        resource_ids=resource_ids,
        screenshots=[s for s in screenshots if s],
        succeeded=True,
    )


async def publish_funnel(task_input: dict[str, Any]) -> BrowserResult:
    """Publish the funnel.

    Only reachable once a human has released the approval hold — the orchestrator
    parks `publish_funnel` in `awaiting_approval` before a worker can claim it.

    TODO(phase-5): implement against the live publish flow.
    """
    raise NotImplementedError(
        "publish_funnel is stubbed until Phase 5. It runs only after human approval."
    )
