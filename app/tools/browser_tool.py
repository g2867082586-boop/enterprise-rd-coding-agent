from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

from app.config import get_settings
from app.security.url_guard import validate_url


def browser_check(
    url: str,
    expected_text: str = "",
    selector: str = "",
    request_id: str = "browser-check",
) -> dict[str, Any]:
    settings = get_settings()
    allowed = {item.strip() for item in settings.browser_allowed_hosts.split(",") if item.strip()}
    validate_url(url, allowed)
    screenshot_dir = settings.project_path("data/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in request_id if c.isalnum() or c in "-_")[:64] or "check"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    screenshot = screenshot_dir / f"{safe_id}-{stamp}.png"
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": settings.browser_headless}
            if settings.browser_channel != "chromium":
                launch_options["channel"] = settings.browser_channel
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.set_default_timeout(settings.browser_timeout_ms)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            response = page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout_ms)
            body = page.locator("body").inner_text()[:4000]
            selector_exists = page.locator(selector).count() > 0 if selector else None
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "ok": bool(response and response.ok) and (not expected_text or expected_text in body)
                and (selector_exists is not False),
                "status": response.status if response else None,
                "title": page.title(),
                "expected_text_found": expected_text in body if expected_text else None,
                "selector_exists": selector_exists,
                "key_text": body[:500],
                "console_errors": console_errors,
                "page_errors": page_errors,
                "screenshot_path": str(screenshot),
                "browser_channel": settings.browser_channel,
            }
            context.close()
            browser.close()
            return result
    except PlaywrightError as exc:
        return {
            "ok": False,
            "error": f"Google Chrome launch or page check failed: {exc}",
            "screenshot_path": None,
            "browser_channel": settings.browser_channel,
        }


async def async_browser_check(
    url: str,
    expected_text: str = "",
    selector: str = "",
    request_id: str = "browser-check",
) -> dict[str, Any]:
    """Async equivalent used by the MCP server's asyncio request loop."""
    settings = get_settings()
    allowed = {item.strip() for item in settings.browser_allowed_hosts.split(",") if item.strip()}
    validate_url(url, allowed)
    screenshot_dir = settings.project_path("data/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    safe_id = "".join(c for c in request_id if c.isalnum() or c in "-_")[:64] or "check"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    screenshot = screenshot_dir / f"{safe_id}-{stamp}.png"
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        async with async_playwright() as playwright:
            launch_options = {"headless": settings.browser_headless}
            if settings.browser_channel != "chromium":
                launch_options["channel"] = settings.browser_channel
            browser = await playwright.chromium.launch(**launch_options)
            context = await browser.new_context(accept_downloads=False)
            page = await context.new_page()
            page.set_default_timeout(settings.browser_timeout_ms)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            response = await page.goto(url, wait_until="networkidle", timeout=settings.browser_timeout_ms)
            body = (await page.locator("body").inner_text())[:4000]
            selector_exists = await page.locator(selector).count() > 0 if selector else None
            await page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "ok": bool(response and response.ok) and (not expected_text or expected_text in body) and (selector_exists is not False),
                "status": response.status if response else None,
                "title": await page.title(),
                "expected_text_found": expected_text in body if expected_text else None,
                "selector_exists": selector_exists,
                "key_text": body[:500],
                "console_errors": console_errors,
                "page_errors": page_errors,
                "screenshot_path": str(screenshot),
                "browser_channel": settings.browser_channel,
            }
            await context.close()
            await browser.close()
            return result
    except PlaywrightError as exc:
        return {"ok": False, "error": f"Google Chrome launch or page check failed: {exc}", "screenshot_path": None, "browser_channel": settings.browser_channel}
