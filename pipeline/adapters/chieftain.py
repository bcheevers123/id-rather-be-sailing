"""Scraper adapter for Chieftain Training (https://chieftain.training/)."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Optional

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import USER_AGENT, PlaywrightAdapter

logger = logging.getLogger(__name__)

PROVIDER_ID = "chieftain-training"
BASE_URL = "https://chieftain.training/"

# XPath to the booking dates table — sourced from direct site inspection
DATES_TABLE_XPATH = (
    "xpath=/html/body/div/div[1]/div[3]/form[1]/div/div[3]/div[6]/table/tbody"
)

# Keyword → course_id mapping; order matters — more specific entries first
COURSE_ID_MAP: list[tuple[list[str], str]] = [
    (["pscrb", "survival craft", "pscrb"], "pscrb"),
    (["pssr", "personal safety and social responsibilities"], "pssr"),
    (["fpff", "fire prevention", "fire fighting and fire prevention"], "fpff"),
    (["aff", "advanced fire"], "aff"),
    (["efa", "elementary first aid", "first aid"], "efa"),
    # Broader matches last so they don't shadow the entries above
    (["pst", "personal survival techniques", "stcw basic", "basic safety"], "pst"),
]


def _infer_course_id(text: str) -> Optional[str]:
    """Return an internal course ID inferred from page title or URL text."""
    lower = text.lower()
    for keywords, course_id in COURSE_ID_MAP:
        if any(kw in lower for kw in keywords):
            return course_id
    return None


_DATE_FORMATS = [
    "%d %b %Y",   # 12 Jan 2025
    "%d %B %Y",   # 12 January 2025
    "%d/%m/%Y",   # 12/01/2025
    "%d-%m-%Y",   # 12-01-2025
    "%Y-%m-%d",   # 2025-01-12
    "%d %b %y",   # 12 Jan 25
    "%d/%m/%y",   # 12/01/25
]


def _parse_date(raw: str) -> Optional[str]:
    """Parse a date string into ISO 8601 (YYYY-MM-DD). Returns None on failure."""
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_price(raw: str) -> Optional[float]:
    """Extract a numeric price from strings such as '£299' or '299.00'."""
    clean = re.sub(r"[£$€,\s]", "", raw)
    m = re.search(r"\d+\.?\d*", clean)
    if m:
        try:
            return float(m.group())
        except ValueError:
            pass
    return None


class ChieftainAdapter(PlaywrightAdapter):
    """Playwright-based scraper for Chieftain Training course dates."""

    def __init__(self) -> None:  # noqa: D107
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch all course offerings from Chieftain Training.

        Returns an empty list if Playwright is not installed or on any error.
        """
        try:
            import playwright  # noqa: F401 — existence check only
        except ImportError:
            logger.warning(
                "playwright is not installed — cannot scrape chieftain.training. "
                "Install it with: pip install playwright && python -m playwright install chromium"
            )
            return []

        try:
            return self._scrape()
        except Exception as exc:
            logger.warning("ChieftainAdapter.fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scrape(self) -> list[Offering]:
        from playwright.sync_api import sync_playwright

        offerings: list[Offering] = []
        today = date.today().isoformat()

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_extra_http_headers({"User-Agent": USER_AGENT})

                # Gather course page URLs from the homepage (and /courses if it exists)
                course_links = self._discover_course_links(page)
                logger.debug("ChieftainAdapter: discovered %d course page(s)", len(course_links))

                for url, course_id in course_links:
                    try:
                        page.goto(url, timeout=30_000)
                        page.wait_for_load_state("networkidle", timeout=15_000)
                        rows = self._get_date_rows(page)
                        for row in rows:
                            offering = self._parse_row(row, course_id, url, today)
                            if offering is not None:
                                offerings.append(offering)
                    except Exception as exc:
                        logger.warning(
                            "ChieftainAdapter: failed to scrape %s: %s", url, exc
                        )
            finally:
                browser.close()

        return offerings

    def _discover_course_links(self, page) -> list[tuple[str, str]]:
        """Return [(url, course_id), ...] for STCW course pages."""
        results: list[tuple[str, str]] = []
        seen: set[str] = set()

        def harvest(p):
            try:
                anchors = p.query_selector_all("a[href]")
            except Exception:
                return
            for anchor in anchors:
                try:
                    href = (anchor.get_attribute("href") or "").strip()
                    text = (anchor.inner_text() or "").strip()
                except Exception:
                    continue

                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue

                # Resolve relative paths
                if href.startswith("/"):
                    href = BASE_URL.rstrip("/") + href
                elif not href.startswith("http"):
                    href = BASE_URL.rstrip("/") + "/" + href

                if "chieftain.training" not in href:
                    continue

                combined = f"{href} {text}"
                course_id = _infer_course_id(combined)
                if course_id and href not in seen:
                    seen.add(href)
                    results.append((href, course_id))

        # Start from the homepage
        page.goto(BASE_URL, timeout=30_000)
        page.wait_for_load_state("networkidle", timeout=15_000)
        harvest(page)

        # Also check a /courses page if it exists and added no new links
        if not results:
            try:
                courses_url = BASE_URL.rstrip("/") + "/courses"
                page.goto(courses_url, timeout=20_000)
                page.wait_for_load_state("networkidle", timeout=10_000)
                harvest(page)
            except Exception:
                pass

        return results

    def _get_date_rows(self, page) -> list:
        """Return table row elements from the booking dates table."""
        # Try the precise XPath first
        try:
            tbody = page.query_selector(DATES_TABLE_XPATH)
            if tbody:
                rows = tbody.query_selector_all("tr")
                if rows:
                    return rows
        except Exception:
            pass

        # Fall back to any table on the page
        try:
            rows = page.query_selector_all("table tbody tr")
            if rows:
                return rows
        except Exception:
            pass

        return []

    def _parse_row(
        self, row, course_id: str, source_url: str, today: str
    ) -> Optional[Offering]:
        """Parse one table row into an Offering. Returns None if no valid date found."""
        try:
            cells = row.query_selector_all("td, th")
            if len(cells) < 2:
                return None

            cell_texts: list[str] = []
            for cell in cells:
                try:
                    cell_texts.append(cell.inner_text().strip())
                except Exception:
                    cell_texts.append("")

            # Skip header-like rows
            if not any(cell_texts):
                return None

            start_date: Optional[str] = None
            end_date: Optional[str] = None
            price: Optional[float] = None
            availability: Optional[str] = None

            for text in cell_texts:
                if not text:
                    continue

                # ---- date detection ----
                if start_date is None:
                    # Direct parse
                    parsed = _parse_date(text)
                    if parsed:
                        start_date = parsed
                        continue

                    # Date range: "12 Jan – 14 Jan 2025" or "12-14 Jan 2025"
                    range_parts = re.findall(
                        r"\d{1,2}\s+\w+(?:\s+\d{2,4})?", text
                    )
                    if range_parts:
                        d0 = _parse_date(range_parts[0])
                        if d0:
                            start_date = d0
                            if len(range_parts) >= 2:
                                end_date = _parse_date(range_parts[-1])
                            continue

                # ---- price detection ----
                if price is None and re.search(r"[£$€]?\s*\d+", text):
                    p = _parse_price(text)
                    if p and p > 0:
                        price = p
                        continue

                # ---- availability detection ----
                if availability is None and re.search(
                    r"\b(available|spaces|places|full|limited|sold.?out|open|closed|book)\b",
                    text,
                    re.IGNORECASE,
                ):
                    availability = text

            if not start_date:
                return None

            return Offering(
                id=f"{course_id}-chieftain-{start_date}",
                course_id=course_id,
                provider_id=PROVIDER_ID,
                start_date=start_date,
                end_date=end_date or start_date,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP" if price is not None else None,
                vat_included=None,
                delivery_format="in_person",
                availability=availability,
                booking_url=source_url,
                source_url=source_url,
                last_verified=today,
            )
        except Exception as exc:
            logger.debug("ChieftainAdapter: row parse error: %s", exc)
            return None
