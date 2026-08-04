"""North Kent College – National Maritime Training Centre adapter.

Scrapes nmtctraining.co.uk (the NMTC-branded sub-site) for STCW course dates.

Structure on each course page:
  - Heading / title carries the course name (used for course_id mapping)
  - Price shown as "£NNN.00" or "£N,NNN.00" in the page body
  - Upcoming dates are a simple <ul> of linked <li> items, e.g.
      <li><a href="https://northkent.collegestore.uk/...">7 September 2026</a></li>
    Multi-day courses show a range anchor text:
      "15-18 September 2026"  (start day - end day Month Year)
      "8 September 2026"      (single day)

The booking URL on each <li> anchor links directly to the collegestore booking page.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://nmtctraining.co.uk"
COURSES_URL = f"{BASE_URL}/courses/all/"

# Category slugs that contain STCW / maritime safety courses
_STCW_CATEGORIES = [
    "nautical",
    "fire-fighting",
    "first-aid",
    "stcw-updating-training",
]

# Maps keywords from course title / URL to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.*fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.*social.resp|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"proficiency.in.medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"proficiency.in.fast.rescue.boats|[^a-z]frb[^a-z]", re.I), "frb"),
    (re.compile(r"proficiency.in.security.awareness|[^a-z]psa[^a-z]", re.I), "pssr"),
    (re.compile(r"basic.safety.training.week", re.I), "pst"),  # BST week = multi-course
]

# "£235" or "£1,080.00"
_PRICE_RE = re.compile(r"£([\d,]+)(?:\.(\d{2}))?")

# Single-day anchor text: "7 September 2026"
_SINGLE_DATE_RE = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$"
)

# Range anchor text: "15-18 September 2026" or "15 - 18 September 2026"
_RANGE_DATE_RE = re.compile(
    r"^(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$"
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date_text(text: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) from an anchor text date string, or (None, None)."""
    text = text.strip()

    m = _RANGE_DATE_RE.match(text)
    if m:
        start_day, end_day, month_str, year_str = m.groups()
        month = _MONTHS.get(month_str.lower())
        if not month:
            return None, None
        try:
            start = datetime(int(year_str), month, int(start_day)).date().isoformat()
            end = datetime(int(year_str), month, int(end_day)).date().isoformat()
            return start, end
        except ValueError:
            return None, None

    m = _SINGLE_DATE_RE.match(text)
    if m:
        day, month_str, year_str = m.groups()
        month = _MONTHS.get(month_str.lower())
        if not month:
            return None, None
        try:
            d = datetime(int(year_str), month, int(day)).date().isoformat()
            return d, d
        except ValueError:
            return None, None

    return None, None


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _extract_price(html_text: str) -> float | None:
    m = _PRICE_RE.search(html_text)
    if not m:
        return None
    try:
        integer_part = m.group(1).replace(",", "")
        decimal_part = m.group(2) or "0"
        return float(f"{integer_part}.{decimal_part}")
    except (ValueError, AttributeError):
        return None


class NorthKentAdapter(BaseAdapter):
    """Adapter for National Maritime Training Centre at North Kent College."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: collect individual course page URLs from all relevant categories
        course_urls: dict[str, str] = {}  # url -> course title hint

        for category in _STCW_CATEGORIES:
            url = f"{COURSES_URL}?course_category={category}"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("NorthKent category fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                new_links = self._extract_course_links(resp.text)
                course_urls.update(new_links)
            except Exception as e:
                logger.warning("NorthKent category parse failed %s: %s", url, e)

        if not course_urls:
            logger.warning("NorthKent: no course links found")
            return []

        # Step 2: scrape each course page for dates
        all_offerings: list[Offering] = []
        for course_url, title_hint in course_urls.items():
            try:
                resp = session.get(course_url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("NorthKent course fetch failed %s: %s", course_url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_course_page(
                    resp.text, course_url, provider, title_hint
                )
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning(
                    "NorthKent course parse failed %s: %s", course_url, e
                )

        logger.info("NorthKent adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _extract_course_links(self, html: str) -> dict[str, str]:
        """Return {absolute_url: anchor_text} for all individual course links."""
        soup = BeautifulSoup(html, "lxml")
        links: dict[str, str] = {}

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            # Course pages live under /course/ (not /courses/)
            if not re.search(r"/course/[^/]+/?$", href):
                continue
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE_URL + href
            else:
                abs_url = BASE_URL + "/" + href
            # Ensure it's on the same domain
            if "nmtctraining.co.uk" not in abs_url:
                continue
            if abs_url not in links:
                links[abs_url] = a.get_text(strip=True)

        return links

    def _parse_course_page(
        self, html: str, page_url: str, provider: dict, title_hint: str
    ) -> list[Offering]:
        """Parse the date list from a single NMTC course page."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course_id from page title or URL
        title_tag = soup.find("h1") or soup.find("title")
        title_text = (
            title_tag.get_text(" ", strip=True) if title_tag else title_hint
        )
        course_id = (
            _course_id_from_text(title_text)
            or _course_id_from_text(page_url)
            or _course_id_from_text(title_hint)
        )
        if not course_id:
            logger.debug(
                "NorthKent: could not determine course_id for %s", page_url
            )
            return []

        # Extract price from page text
        price = _extract_price(soup.get_text())

        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        # Find all <a> tags whose text looks like a date and href points to collegestore
        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if "collegestore" not in href and "northkent.ac.uk/store" not in href:
                continue
            link_text = a.get_text(strip=True)
            start_iso, end_iso = _parse_date_text(link_text)
            if not start_iso:
                continue
            if start_iso in seen_dates:
                continue
            seen_dates.add(start_iso)

            booking_url = safe_url(href)
            provider_slug = "nmtc"

            offerings.append(
                Offering(
                    id=f"{course_id}-{provider_slug}-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP",
                    vat_included=False,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=booking_url,
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "NorthKent: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
