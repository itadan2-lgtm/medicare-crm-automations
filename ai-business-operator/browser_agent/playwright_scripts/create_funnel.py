"""Create funnel steps in the systeme.io UI.

The funnel itself is created through the Public API — it is faster and returns IDs
reliably. This script covers the parts the API does not expose: template selection
and step layout inside the funnel editor.

TODO(phase-5): the selectors below are written from the documented UI copy and need
verifying against the live editor. Run headed (`PLAYWRIGHT_HEADLESS=false`) the
first time and correct the accessible names rather than reaching for CSS selectors.
"""

from __future__ import annotations

import logging

from playwright.async_api import Page

from browser_agent.playwright_scripts.base import capture_failure

log = logging.getLogger(__name__)

FUNNELS_URL = "https://systeme.io/dashboard/funnels"


async def open_funnel(page: Page, funnel_name: str) -> None:
    await page.goto(FUNNELS_URL)
    await page.get_by_role("link", name=funnel_name).click()
    await page.wait_for_load_state("networkidle")
    log.info("browser.funnel_opened", extra={"funnel": funnel_name})


async def add_step(page: Page, step_type: str, step_name: str) -> str:
    """Add one funnel step and return its id from the resulting URL.

    Raises on failure after capturing a screenshot — a silently skipped step would
    produce a funnel that looks built and is not.
    """
    try:
        await page.get_by_role("button", name="Add step").click()
        await page.get_by_label("Step name").fill(step_name)
        await page.get_by_role("radio", name=_step_label(step_type)).check()
        await page.get_by_role("button", name="Create").click()
        await page.wait_for_url("**/funnel_step/**")

        step_id = page.url.rstrip("/").split("/")[-1]
        log.info(
            "browser.step_added",
            extra={"step_type": step_type, "step_name": step_name, "step_id": step_id},
        )
        return step_id
    except Exception:
        await capture_failure(page, f"add_step-{step_type}")
        raise


async def select_template(page: Page, template_name: str) -> None:
    try:
        await page.get_by_role("button", name="Choose template").click()
        await page.get_by_role("heading", name=template_name).click()
        await page.get_by_role("button", name="Select").click()
        await page.wait_for_load_state("networkidle")
        log.info("browser.template_selected", extra={"template": template_name})
    except Exception:
        await capture_failure(page, "select_template")
        raise


def _step_label(step_type: str) -> str:
    """Map our internal step types to the labels shown in the systeme.io UI."""
    labels = {
        "optin": "Squeeze page",
        "sales": "Sales page",
        "checkout": "Order page",
        "upsell": "Upsell page",
        "thankyou": "Thank you page",
    }
    try:
        return labels[step_type]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported step type {step_type!r}; expected one of {', '.join(labels)}"
        ) from exc
