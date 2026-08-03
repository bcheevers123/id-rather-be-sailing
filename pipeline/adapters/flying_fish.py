"""Adapter for Flying Fish UK Ltd.

Flying Fish runs STCW courses (PST, EFA, FPFF, PSSR) from their Cowes base.
Course booking pages are at flyingfishonline.com/shop/course/... and each page
contains a <select> element with available dates for that course.

Strategy:
1. Navigate to the STCW/safety-training section of the Flying Fish shop.
2. Collect links to individual course pages that match STCW course names.
3. On each course page, locate the date <select> element and read all options.
4. Parse each option's text as a date and emit an Offering per (course, date).

Playwright is required because the shop pages are JS-rendered. If it is not
installed, fetch() returns [] gracefully.
"""
import logging
import re
from datetime import datetime, timezone

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

PROVIDER_ID = "flying-fish-uk-ltd"
BASE_URL = "https://www.flyingfishonline.com"

# Entry points to try for the STCW/safety-training course catalogue.
_SHOP_URLS = [
    "https://www.flyingfishonline.com/shop/course/stcw/",
    "https://www.flyingfishonline.com/shop/course/safety-training/",
    "https://www.flyingfishonline.com/shop/course/",
]

# Map fragments found in course page titles/headings → canonical course_id.
# More specific patterns first to avoid false matches.
_LABEL_MAP: list[tuple[str, str]] = [
    ("personal survival techniques", "pst"),
    ("personal survival", "pst"),
    (" pst", "pst"),
    ("elementary first aid", "efa"),
    (" efa", "efa"),
    ("fire prevention and fire fighting", "fpff"),
    ("fire prevention and firefighting", "fpff"),
    ("fire prevention", "fpff"),
    ("fpff", "fpff"),
    ("personal safety and social responsibility", "pssr"),
    ("personal safety", "pssr"),
    ("pssr", "pssr"),
    ("basic safety training", "pst"),
]

# Date strings that appear in <select> option text vary by site.
# Examples: "15/08/2026", "15 Aug 2026", "August 15, 2026", "Mon 15 Aug 2026"
_DATE_PATTERNS: list[re.Pattern] = [
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"),
    # "15 Aug 2026" or "15 August 2026"
    re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})"),
    # "Aug 15 2026" or "August 15, 2026"
    re.compile(r"([A-Za-z]{3,9})\s+(\d{1,2})[,\s]+(\d{4})"),
]

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _map_label(text: str) -> str | None:
    """Return course_id for a title/heading string, or None if unrecognised."""
    lower = text.lower()
    for fragment, course_id in _LABEL_MAP:
        if fragment in lower:
            return course_id
    return None


def _parse_date(text: str) -> str | None:
    """Try to parse a date from an option label. Returns ISO date or None."""
    t = text.strip()
    # Pattern 1: DD/MM/YYYY
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", t)
    if m:
        try:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return d.date().isoformat()
        except ValueError:
            pass

    # Pattern 2: "15 Aug 2026"
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", t)
    if m:
        month = _MONTH_NAMES.get(m.group(2).lower())
        if month:
            try:
                d = datetime(int(m.group(3)), month, int(m.group(1)))
                return d.date().isoformat()
            except ValueError:
                pass

    # Pattern 3: "Aug 15, 2026"
    m = re.search(r"([A-Za-z]{3,9})\s+(\d{1,2})[,\s]+(\d{4})", t)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        if month:
            try:
                d = datetime(int(m.group(3)), month, int(m.group(2)))
                return d.date().isoformat()
            except ValueError:
                pass

    # Fallback: dateutil if available
    try:
        from dateutil import parser as dateutil_parser
        return dateutil_parser.parse(t, fuzzy=True).date().isoformat()
    except Exception:
        pass

    return None


class FlyingFishAdapter(PlaywrightAdapter):
    """Fetches STCW course dates from Flying Fish UK Ltd.

    Uses Playwright to navigate course catalogue pages and extract available
    dates from the booking <select> dropdown on each individual course page.
    """

    def __init__(self) -> None:
        pass  # No per-instance state needed

    def fetch(self, provider: dict) -> list[Offering]:  # noqa: C901
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning(
                "playwright is not installed — cannot scrape Flying Fish. "
                "Install with: pip install playwright && python -m playwright install chromium"
            )
            return []

        try:
            return self._scrape(provider)
        except Exception as e:
            logger.warning("FlyingFish: unexpected error during scrape: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal scraping logic
    # ------------------------------------------------------------------

    def _scrape(self, provider: dict) -> list[Offering]:
        from playwright.sync_api import sync_playwright

        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
                "+https://github.com/bcheevers123/id-rather-be-sailing)"
            ))
            page = context.new_page()

            # Step 1: find course listing page links
            course_links = self._find_stcw_course_links(page)
            if not course_links:
                logger.info(
                    "FlyingFish: no STCW course pages found — site structure may have changed"
                )
                browser.close()
                return []

            logger.info("FlyingFish: found %d STCW course page(s)", len(course_links))

            # Step 2: visit each course page and extract dates from select
            seen: set[str] = set()
            for course_id, course_url, course_title in course_links:
                page_offerings = self._scrape_course_page(
                    page, course_id, course_url, course_title, provider, now, seen
                )
                offerings.extend(page_offerings)

            browser.close()

        logger.info("FlyingFish: extracted %d offering(s) in total", len(offerings))
        return offerings

    def _find_stcw_course_links(self, page) -> list[tuple[str, str, str]]:
        """Return list of (course_id, url, title) for STCW course pages."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        found: dict[str, tuple[str, str, str]] = {}  # url → (course_id, url, title)

        for shop_url in _SHOP_URLS:
            try:
                page.goto(shop_url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeout:
                logger.info("FlyingFish: timeout loading %s, trying next URL", shop_url)
                continue
            except Exception as e:
                logger.info("FlyingFish: failed to load %s: %s", shop_url, e)
                continue

            # Collect all anchor links on the page
            links = page.query_selector_all("a[href]")
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()
                except Exception:
                    continue

                # Normalise to absolute URL
                if href.startswith("/"):
                    href = BASE_URL + href
                if not href.startswith(BASE_URL):
                    continue
                # Must look like a course page (contains /shop/course/ and a slug)
                if "/shop/course/" not in href:
                    continue
                # Skip pagination or category-only links (no trailing slug segment)
                # A course page URL typically has ≥4 path segments after /shop/course/
                path_parts = [p for p in href.rstrip("/").split("/") if p]
                if len(path_parts) < 4:
                    continue

                course_id = _map_label(text)
                if course_id and href not in found:
                    found[href] = (course_id, href, text)

            if found:
                # Got some results from this entry point — no need to try others
                break

        # If nothing from category browsing, try known direct URL patterns
        if not found:
            logger.info(
                "FlyingFish: catalogue pages yielded no STCW links; "
                "trying known course slug patterns"
            )
            direct_urls = self._probe_direct_urls(page)
            for course_id, url, title in direct_urls:
                if url not in found:
                    found[url] = (course_id, url, title)

        return list(found.values())

    def _probe_direct_urls(self, page) -> list[tuple[str, str, str]]:
        """Try a small set of guessed course page URLs and return those that load."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        candidates = [
            ("pst",  "https://www.flyingfishonline.com/shop/course/stcw/personal-survival-techniques/",
             "Personal Survival Techniques"),
            ("efa",  "https://www.flyingfishonline.com/shop/course/stcw/elementary-first-aid/",
             "Elementary First Aid"),
            ("fpff", "https://www.flyingfishonline.com/shop/course/stcw/fire-prevention-and-fire-fighting/",
             "Fire Prevention and Fire Fighting"),
            ("pssr", "https://www.flyingfishonline.com/shop/course/stcw/personal-safety-and-social-responsibility/",
             "Personal Safety and Social Responsibility"),
        ]
        valid: list[tuple[str, str, str]] = []
        for course_id, url, title in candidates:
            try:
                resp = page.goto(url, timeout=20000)
                if resp and resp.status < 400:
                    valid.append((course_id, url, title))
            except (PlaywrightTimeout, Exception):
                continue
        return valid

    def _scrape_course_page(
        self,
        page,
        course_id: str,
        course_url: str,
        course_title: str,
        provider: dict,
        now: str,
        seen: set,
    ) -> list[Offering]:
        """Navigate to one course page and extract dates from the date selector."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        offerings: list[Offering] = []

        try:
            page.goto(course_url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            logger.info("FlyingFish: timeout loading course page %s", course_url)
            return []
        except Exception as e:
            logger.info("FlyingFish: error loading course page %s: %s", course_url, e)
            return []

        # Look for a <select> element that contains date-like options.
        # The booking form typically has id/name containing "date" or similar.
        date_options: list[str] = []

        # Try common selectors for booking date dropdowns
        select_selectors = [
            "select[name*='date']",
            "select[id*='date']",
            "select[class*='date']",
            "select[name*='Date']",
            "select[id*='Date']",
            "form select",   # any select inside a form
            "select",        # fallback: any select on page
        ]

        for selector in select_selectors:
            try:
                selects = page.query_selector_all(selector)
            except Exception:
                continue

            for select_el in selects:
                try:
                    options = select_el.query_selector_all("option")
                except Exception:
                    continue

                option_texts = []
                for opt in options:
                    try:
                        val = opt.inner_text().strip()
                        if val:
                            option_texts.append(val)
                    except Exception:
                        continue

                # Check if at least one option looks like a date
                date_like = [t for t in option_texts if _parse_date(t) is not None]
                if date_like:
                    date_options = date_like
                    break

            if date_options:
                break

        if not date_options:
            # Try parsing the page HTML via BeautifulSoup as a secondary approach
            date_options = self._find_dates_in_html(page.content(), course_url)

        if not date_options:
            logger.info(
                "FlyingFish: no date options found on %s (course: %s)",
                course_url, course_id,
            )
            return []

        for option_text in date_options:
            start_date = _parse_date(option_text)
            if not start_date:
                continue

            offering_id = f"{course_id}-flying-fish-{start_date}"
            if offering_id in seen:
                continue
            seen.add(offering_id)

            offerings.append(Offering(
                id=offering_id,
                course_id=course_id,
                provider_id=provider.get("id", PROVIDER_ID),
                start_date=start_date,
                end_date=start_date,
                timezone="Europe/London",
                duration_days=None,
                price=None,
                currency=None,
                vat_included=None,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(course_url),
                source_url=course_url,
                last_verified=now,
                freshness_status="verified",
            ))

        logger.info(
            "FlyingFish: %d offering(s) from %s (%s)",
            len(offerings), course_title, course_id,
        )
        return offerings

    def _find_dates_in_html(self, html: str, source_url: str) -> list[str]:
        """Secondary fallback: parse select options from raw HTML via BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        soup = BeautifulSoup(html, "lxml")
        for select in soup.find_all("select"):
            options = [o.get_text(strip=True) for o in select.find_all("option")]
            date_like = [t for t in options if _parse_date(t) is not None]
            if date_like:
                return date_like

        return []
