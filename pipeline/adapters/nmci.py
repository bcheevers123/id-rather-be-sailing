"""National Maritime College of Ireland (nmci.ie) adapter.

Scrapes the NMCI Training Services short-course catalogue at
https://www.nmci.ie/short_courses/

Each course page at /short_courses/courseId/<N>/ contains:
  - A <div class="copy"> block with structured h4/p pairs for
    "Course Name:", "Course Price:", etc.
  - A <ul class="dates"> block whose <li> items each hold an
    <a class="courseDateIdLink"> with:
      - visible text containing the start date as DD/MM/YYYY
      - an onclick attribute containing the booking URL as
        NMCI.Booking.AddToCart(<id>, '<https://...courseDateId=N>')

robots.txt: No Disallow rules block /short_courses/.
Crawl-delay: not specified; we honour a 2 s minimum between requests.

STCW course IDs scraped:
  pst    — courseId/15  (Personal Survival Techniques)
  pssr   — courseId/16  (Personal Safety & Social Responsibility)
  fpff   — courseId/18  (Fire Prevention & Fire Fighting, 2.5-day)
  aff    — courseId/19  (Advanced Fire Fighting, 4-day)
  efa    — courseId/20  (Elementary First Aid)
  pscrb  — courseId/40  (Proficiency in Survival Craft & Rescue Boats)
  mc     — courseId/48699913 (Medical Care Aboard Ship)
  mfa    — courseId/48699942 (Medical First Aid)
  frb    — courseId/48700004 (Proficiency in Fast Rescue Boats)
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

BASE_URL = "https://www.nmci.ie"
TIMEZONE = "Europe/Dublin"

# Maps (course_id, course_url_path) tuples for every STCW course offered.
# Duration is in days (inclusive); None = unknown from name alone.
_COURSES: list[tuple[str, str, float | None]] = [
    ("pst",   "/short_courses/courseId/15/",       1.0),
    ("pssr",  "/short_courses/courseId/16/",        1.0),
    ("fpff",  "/short_courses/courseId/18/",        2.5),
    ("aff",   "/short_courses/courseId/19/",        4.0),
    ("efa",   "/short_courses/courseId/20/",        1.0),
    ("pscrb", "/short_courses/courseId/40/",        3.0),
    ("mc",    "/short_courses/courseId/48699913/",  5.0),
    ("mfa",   "/short_courses/courseId/48699942/",  3.0),
    ("frb",   "/short_courses/courseId/48700004/",  3.0),
]

# Matches euro prices like "€ 385", "€890", "€1,195", "€ 1 195.00"
_PRICE_RE = re.compile(r"€\s*([\d,\s]+(?:\.\d+)?)")

# Extracts the booking URL from onclick="NMCI.Booking.AddToCart(ID,'URL');"
_ONCLICK_URL_RE = re.compile(r"AddToCart\(\d+,\s*'([^']+)'")

# Matches dates formatted as DD/MM/YYYY
_DATE_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


def _parse_date(text: str) -> str | None:
    """Parse DD/MM/YYYY text → ISO 'YYYY-MM-DD'. Returns None on failure."""
    m = _DATE_RE.search(text)
    if not m:
        return None
    day, month, year = m.group(1), m.group(2), m.group(3)
    try:
        dt = datetime(int(year), int(month), int(day))
        return dt.date().isoformat()
    except ValueError:
        return None


def _end_date(start_iso: str, duration_days: float | None) -> str:
    """Compute end date from start ISO string and duration. Falls back to start_date."""
    if not duration_days or duration_days <= 1:
        return start_iso
    try:
        from datetime import date, timedelta
        s = date.fromisoformat(start_iso)
        # inclusive end: duration 2.5 days means 3 calendar days (Mon–Wed)
        end = s + timedelta(days=int(duration_days) - 1)
        return end.isoformat()
    except (ValueError, TypeError):
        return start_iso


def _parse_price(html_text: str) -> float | None:
    """Extract the first euro price from a block of text. Returns None if absent."""
    m = _PRICE_RE.search(html_text)
    if not m:
        return None
    raw = m.group(1).replace(",", "").replace(" ", "")
    try:
        return float(raw)
    except ValueError:
        return None


class NmciAdapter(BaseAdapter):
    """Adapter for the National Maritime College of Ireland short courses."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        all_offerings: list[Offering] = []

        for course_id, path, duration in _COURSES:
            url = BASE_URL + path
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("nmci.ie: fetch failed for %s: %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_course_page(
                    resp.text, url, course_id, duration, provider, now
                )
                all_offerings.extend(offerings)
                logger.info(
                    "nmci.ie: %d offerings for course_id=%s (%s)",
                    len(offerings),
                    course_id,
                    url,
                )
            except Exception as exc:
                logger.warning("nmci.ie: parse failed for %s: %s", url, exc)

        logger.info("nmci.ie adapter: %d offerings total", len(all_offerings))
        return all_offerings

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _parse_course_page(
        self,
        html: str,
        page_url: str,
        course_id: str,
        duration_days: float | None,
        provider: dict,
        now: str,
    ) -> list[Offering]:
        """Parse one NMCI course page and return Offering objects (one per date)."""
        soup = BeautifulSoup(html, "lxml")
        copy_div = soup.find("div", class_="copy")
        if not copy_div:
            logger.debug("nmci.ie: no .copy div on %s", page_url)
            return []

        # Extract price from the "Course Price:" h4/p pair
        price: float | None = None
        price_heading = copy_div.find("h4", string=lambda t: t and "Course Price" in t)
        if price_heading:
            price_p = price_heading.find_next_sibling("p")
            if price_p:
                price = _parse_price(price_p.get_text())

        # Extract dates from <ul class="dates"> → <a class="courseDateIdLink">
        dates_ul = copy_div.find("ul", class_="dates")
        if not dates_ul:
            logger.debug("nmci.ie: no dates list on %s", page_url)
            return []

        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        for a_tag in dates_ul.find_all("a", class_="courseDateIdLink"):
            date_text = a_tag.get_text(" ", strip=True)
            start_iso = _parse_date(date_text)
            if not start_iso or start_iso in seen_dates:
                continue
            seen_dates.add(start_iso)

            # Extract booking URL from onclick attribute
            onclick = a_tag.get("onclick", "")
            booking_url: str | None = None
            m = _ONCLICK_URL_RE.search(onclick)
            if m:
                booking_url = safe_url(m.group(1))

            end_iso = _end_date(start_iso, duration_days)
            offering_id = f"{course_id}-nmci-{start_iso}"

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone=TIMEZONE,
                    duration_days=duration_days,
                    price=price,
                    currency="EUR",
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=booking_url,
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
