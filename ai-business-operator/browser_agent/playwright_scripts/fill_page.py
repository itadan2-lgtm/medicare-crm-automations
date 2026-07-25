"""Fill page content in the systeme.io page editor.

The page editor is the clearest case for browser automation: the API can save page
content wholesale, but placing copy into specific blocks and applying brand colours
is UI work.

TODO(phase-5): verify accessible names against the live editor. Prefer asking the
systeme.io team to expose `data-test-id` attributes over hardening these selectors.
"""

from __future__ import annotations

import logging

from playwright.async_api import Page

from browser_agent.playwright_scripts.base import capture_failure

log = logging.getLogger(__name__)


async def open_editor(page: Page, page_id: str) -> None:
    await page.goto(f"https://systeme.io/dashboard/page_editor/{page_id}")
    await page.wait_for_load_state("networkidle")


async def set_text_block(page: Page, block_label: str, text: str) -> None:
    """Replace the text of a named block."""
    try:
        block = page.get_by_role("textbox", name=block_label)
        await block.click()
        await block.fill(text)
        log.info("browser.block_filled", extra={"block": block_label})
    except Exception:
        await capture_failure(page, f"set_text-{block_label}")
        raise


async def apply_copy(page: Page, copy_blocks: dict[str, str]) -> list[str]:
    """Write a copy agent's output into the editor.

    Returns the labels actually written. A missing block is logged and skipped
    rather than raising — a page with four of five blocks filled is still worth
    saving, and the caller reports the difference.
    """
    written: list[str] = []
    label_map = {
        "headline": "Headline",
        "subheadline": "Subheadline",
        "body": "Body text",
        "cta": "Button text",
    }

    for key, label in label_map.items():
        value = copy_blocks.get(key)
        if not value:
            continue
        try:
            await set_text_block(page, label, str(value))
            written.append(key)
        except Exception:  # noqa: BLE001 - one missing block must not lose the rest
            log.warning("browser.block_missing", extra={"block": label})

    return written


async def apply_palette(page: Page, palette: list[str]) -> None:
    """Apply brand colours to the page theme."""
    if not palette:
        return
    try:
        await page.get_by_role("button", name="Theme").click()
        await page.get_by_label("Primary color").fill(palette[0])
        if len(palette) > 1:
            await page.get_by_label("Accent color").fill(palette[1])
        log.info("browser.palette_applied", extra={"colors": len(palette)})
    except Exception:
        await capture_failure(page, "apply_palette")
        raise


async def save(page: Page) -> None:
    try:
        await page.get_by_role("button", name="Save").click()
        # Wait for the confirmation, not for a duration — a fixed sleep here would
        # either be flaky or slow, and usually both.
        await page.get_by_text("Saved").wait_for(state="visible")
        log.info("browser.page_saved")
    except Exception:
        await capture_failure(page, "save_page")
        raise
