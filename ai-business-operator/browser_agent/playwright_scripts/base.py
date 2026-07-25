"""Shared Playwright session handling.

Locator rules, in order of preference:

1. `get_by_role()` / `get_by_label()` — semantic, survives CSS and layout changes.
2. `get_by_text()` — acceptable for buttons and headings with stable wording.
3. `data-test-id` — if systeme.io exposes one, prefer it over anything else.
4. CSS class selectors — no. They break on every systeme.io release.
5. XPath — no.

Playwright auto-waits for elements to be actionable. Do not add `sleep()`; if
something needs waiting on, express it as a condition (`expect_navigation`,
`wait_for_selector`), not as a duration.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

log = logging.getLogger(__name__)

SYSTEMEIO_LOGIN_URL = "https://systeme.io/dashboard/login"
DEFAULT_TIMEOUT_MS = 30_000


def artifact_dir() -> Path:
    path = Path(os.getenv("PLAYWRIGHT_ARTIFACT_DIR", "./artifacts"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@asynccontextmanager
async def browser_session(
    *, headless: bool | None = None, record_trace: bool = True
) -> AsyncGenerator[tuple[Browser, BrowserContext, Page], None]:
    """One isolated browser session.

    Each session gets a fresh context — no cookies or storage carry over between
    runs, so one project's state can never leak into another's.
    """
    if headless is None:
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO_MS", "0"))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)

        if record_trace:
            await context.tracing.start(screenshots=True, snapshots=True)

        page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            if record_trace:
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
                await context.tracing.stop(path=str(artifact_dir() / f"trace-{stamp}.zip"))
            await context.close()
            await browser.close()


async def login(page: Page, email: str, password: str) -> None:
    """Sign in to systeme.io.

    TODO(phase-5): verify these labels against the live login form and switch to a
    stored storage_state so most runs skip the login round-trip entirely.
    """
    await page.goto(SYSTEMEIO_LOGIN_URL)
    await page.get_by_label("Email").fill(email)
    await page.get_by_label("Password").fill(password)
    await page.get_by_role("button", name="Log in").click()
    await page.wait_for_url("**/dashboard**")
    log.info("browser.logged_in")


async def capture_failure(page: Page, label: str) -> str:
    """Screenshot on failure. Never swallow the error that prompted this."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    path = artifact_dir() / f"{label}-{stamp}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:  # noqa: BLE001 - a failed screenshot must not mask the real error
        log.warning("browser.screenshot_failed", extra={"label": label})
        return ""
    log.info("browser.screenshot", extra={"label": label, "path": str(path)})
    return str(path)
