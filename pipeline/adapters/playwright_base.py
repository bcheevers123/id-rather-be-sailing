"""Base adapter for sites that require JavaScript rendering via Playwright."""
import logging

from pipeline.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"


class PlaywrightAdapter(BaseAdapter):
    """Base for adapters that need a headless browser.

    Subclasses call ``fetch_rendered`` to retrieve JS-rendered page HTML.
    If Playwright is not installed, ``fetch_rendered`` logs a warning and
    returns an empty string so the adapter can degrade gracefully.
    """

    def fetch_rendered(self, url: str, wait_selector: str = None, timeout: int = 30000) -> str:
        """Fetch a JS-rendered page. Returns HTML string or empty string on failure."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning(
                "playwright is not installed — cannot fetch %s. "
                "Install it with: pip install playwright && python -m playwright install chromium",
                url,
            )
            return ""

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": USER_AGENT})
                page.goto(url, timeout=timeout)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=10000)
                else:
                    page.wait_for_load_state("networkidle", timeout=15000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.warning("Playwright fetch failed for %s: %s", url, e)
            return ""
