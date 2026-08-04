"""Adapter for Hamble School of Yachting (hamble.co.uk).

Scrapes STCW course pages for available dates. The site is a WordPress
installation. Single-day courses (PST, EFA) list upcoming dates as
<option> elements in a booking-form <select>. Multi-day courses (MFA, MC)
show dates as prose ranges in the page body (e.g. "Monday 26 October 2026
- Thursday 29 October 2026").

Robots.txt: allow all crawlers (allow: /).
Delay: 2 s between requests (no crawl-delay directive on the site).

STCW courses offered (scouted 2026-08-04):
  PST  https://www.hamble.co.uk/mca-stcw-courses/mca-stcw-personal-survival-techniques
         £155 per person, 1 day, ~20 upcoming dates
  EFA  https://www.hamble.co.uk/mca-stcw-elementary-first-aid
         £150 per person, 1 day
  MFA  https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-first-aid-on-board-ship
         £515 per person, 4 days
  MC   https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-care-on-board-ship
         £655 per person, 5 days
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.hamble.co.uk"

# Course pages verified by scouting 2026-08-04.
# Tuple: (url, default_price_gbp, duration_days)
_COURSE_PAGES: dict[str, tuple[str, float | None, int | None]] = {
    "pst": (
        "https://www.hamble.co.uk/mca-stcw-courses/mca-stcw-personal-survival-techniques",
        155.0,
        1,
    ),
    "efa": (
        "https://www.hamble.co.uk/mca-stcw-elementary-first-aid",
        150.0,
        1,
    ),
    "mfa": (
        "https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-first-aid-on-board-ship",
        515.0,
        4,
    ),
    "mc": (
        "https://www.hamble.co.uk/mca-stcw-proficiency-in-medical-care-on-board-ship",
        655.0,
        5,
    ),
}

# Date pattern: "Sat 29 Aug 2026", "Saturday 29 August 2026", "Mon 02 Nov 2026" etc.
_DATE_RE = re.compile(
    r"\b(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|"
    r"Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"\s+\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b",
    re.I,
)

# Date-range pattern: "Monday 26 October 2026 - Thursday 29 October 2026"
_DATE_RANGE_RE = re.compile(
    r"("
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|"
    r"Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"\s+\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r")"
    r"\s*[-–to]+\s*"
    r"("
    r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|"
    r"Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
    r"\s+\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r")",
    re.I,
)

_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")


class HambleAdapter(BaseAdapter):
    """Fetches STCW course dates from Hamble School of Yachting.

    Uses requests + BeautifulSoup to parse static WordPress pages.
    Dates are read from <option> elements (PST/EFA booking forms) or
    from prose date-range text (MFA/MC course pages).
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        offerings: list[Offering] = []

        for course_id, (url, default_price, duration_days) in _COURSE_PAGES.items():
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Hamble fetch failed %s: %s", url, e)
                time.sleep(2)
                continue

            time.sleep(2)

            try:
                page_offerings = _parse_course_page(
                    resp.text,
                    source_url=url,
                    course_id=course_id,
                    default_price=default_price,
                    duration_days=duration_days,
                    provider=provider,
                )
                offerings.extend(page_offerings)
            except Exception as e:
                logger.warning("Hamble parse failed %s: %s", url, e)

        logger.info("Hamble adapter: %d offerings extracted", len(offerings))
        return offerings


# ---------------------------------------------------------------------------
# Parsing helpers (module-level for testability)
# ---------------------------------------------------------------------------

def _parse_course_page(
    html: str,
    source_url: str,
    course_id: str,
    default_price: float | None,
    duration_days: int | None,
    provider: dict,
) -> list[Offering]:
    """Extract Offering objects from a single Hamble course page."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    # Try to extract price from page text; fall back to scouted default.
    page_text = soup.get_text(" ", strip=True)
    page_price = _extract_price(page_text) or default_price

    # Strategy 1: <option> elements in a booking-form <select>.
    # PST and EFA use a select dropdown populated with upcoming dates.
    date_pairs = _dates_from_options(soup)

    # Strategy 2: prose date ranges in page body text.
    # MFA and MC pages list dates as "Monday DD Month YYYY - Thursday DD Month YYYY".
    if not date_pairs:
        date_pairs = _dates_from_text(page_text)

    for start_date, end_date in date_pairs:
        if start_date in seen:
            continue
        seen.add(start_date)

        offerings.append(
            Offering(
                id=f"{course_id}-hamble-{start_date}",
                course_id=course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=end_date,
                timezone="Europe/London",
                duration_days=float(duration_days) if duration_days else None,
                price=page_price,
                currency="GBP" if page_price is not None else None,
                vat_included=None,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(source_url),
                source_url=source_url,
                last_verified=now,
                freshness_status="verified",
            )
        )

    logger.info(
        "Hamble: %d offerings from %s (%s)", len(offerings), source_url, course_id
    )
    return offerings


def _dates_from_options(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Scan <option> elements for date strings; return (start, end) pairs."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for option in soup.find_all("option"):
        text = option.get_text(strip=True)
        pair = _parse_date_range(text)
        if pair:
            start, _ = pair
            if start not in seen:
                seen.add(start)
                results.append(pair)

    return results


def _dates_from_text(text: str) -> list[tuple[str, str]]:
    """Scan page text for date patterns; return (start, end) pairs."""
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Try date-range patterns first ("Mon DD Month YYYY - Thu DD Month YYYY").
    for m in _DATE_RANGE_RE.finditer(text):
        start = _parse_one_date(m.group(1))
        end = _parse_one_date(m.group(2))
        if start and end and start not in seen:
            seen.add(start)
            results.append((start, end))

    # Fall back to individual date mentions if no ranges found.
    if not results:
        for m in _DATE_RE.finditer(text):
            d = _parse_one_date(m.group(0))
            if d and d not in seen:
                seen.add(d)
                results.append((d, d))

    return results


def _parse_date_range(text: str) -> tuple[str, str] | None:
    """Parse a string that may be a single date or a date range.

    Returns (start_iso, end_iso) or None if no date found.
    """
    m = _DATE_RANGE_RE.search(text)
    if m:
        start = _parse_one_date(m.group(1))
        end = _parse_one_date(m.group(2))
        if start and end:
            return start, end

    m_single = _DATE_RE.search(text)
    if m_single:
        d = _parse_one_date(m_single.group(0))
        if d:
            return d, d

    return None


def _parse_one_date(text: str) -> str | None:
    """Parse a date string like 'Sat 29 Aug 2026' into ISO YYYY-MM-DD."""
    try:
        return dateutil_parser.parse(text, fuzzy=True).date().isoformat()
    except Exception:
        return None


def _extract_price(text: str) -> float | None:
    """Extract the first £ price from text; return as float or None."""
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None
