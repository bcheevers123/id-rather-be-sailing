"""ASET International Energy Training Academy adapter for aset.co.uk.

Site overview
-------------
ASET International Energy Training Academy is based in Aberdeen and offers
industrial and maritime training including GMDSS radio courses.

robots.txt
----------
aset.co.uk/robots.txt returns HTTP 404 — no robots.txt exists.  No Disallow
rules apply.

Radio / GMDSS courses confirmed (as of 2026-08-04)
----------------------------------------------------
  goc  → /training-courses/marine-operations/radiotelephony-general-opearators-certificate-goc-gmdss
          9 days, £1,726.00 per delegate
  roc  → /training-courses/marine-operations/radiotelephony-restricted-operators-certificate-roc-gmdss
          3 days, £984.00 per delegate

Schedule approach
-----------------
The ASET website does not expose a public course calendar.  Individual course
pages list price and duration but contain no upcoming run dates.  Booking is
handled by contacting asetbookings@aset.co.uk directly.

The adapter fetches each course page to:
  1. Confirm the course is still listed (i.e. not removed from the site).
  2. Extract any date information if ASET adds a schedule section in future.
  3. Extract the current price, in case it changes.

If no parseable dates are found (the current situation), the adapter returns []
rather than fabricating data.  All prices and durations hardcoded below are
taken from live page reads performed on 2026-08-04 and are used only as a
fallback if extraction fails.

A 2-second delay is observed between requests to the same domain.
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

BASE_URL = "https://aset.co.uk"
CONTACT_URL = "https://aset.co.uk/contact"

# Minimum delay between HTTP requests to the same domain (seconds)
_REQUEST_DELAY = 2.0

# Adapter slug used in offering IDs
_ADAPTER_SLUG = "aset"

# Known course pages: (course_id, path, duration_days, fallback_price_gbp)
_COURSE_PAGES: list[tuple[str, str, float, float]] = [
    (
        "goc",
        "/training-courses/marine-operations/"
        "radiotelephony-general-opearators-certificate-goc-gmdss",
        9.0,
        1726.0,
    ),
    (
        "roc",
        "/training-courses/marine-operations/"
        "radiotelephony-restricted-operators-certificate-roc-gmdss",
        3.0,
        984.0,
    ),
]

# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"[£]\s*([\d,]+(?:\.\d{2})?)")


def _extract_price(text: str) -> float | None:
    """Extract the first GBP price found in page text."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

# Patterns we look for in a "Upcoming Dates" / "Course Dates" table or list.
# Examples: "06 Oct 2026", "6th October 2026", "Mon 6 Oct 2026 – Fri 14 Oct 2026"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})"
    r"\s*[-–—to]+\s*"
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    re.I,
)
_SINGLE_DATE_RE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    re.I,
)


def _parse_date_ranges(text: str) -> list[tuple[str, str]]:
    """
    Scan page text for date ranges or single dates that look like course
    run dates.  Returns a list of (start_iso, end_iso) pairs.

    Called on sections of page text that are near keywords like
    "upcoming", "dates", "schedule", "availability".
    """
    results: list[tuple[str, str]] = []

    for m in _DATE_RANGE_RE.finditer(text):
        d1, mo1, y1 = m.group(1), m.group(2), m.group(3)
        d2, mo2, y2 = m.group(4), m.group(5), m.group(6)
        try:
            start = dateutil_parser.parse(f"{d1} {mo1} {y1}").date().isoformat()
            end = dateutil_parser.parse(f"{d2} {mo2} {y2}").date().isoformat()
            results.append((start, end))
        except Exception:
            pass

    if results:
        return results

    # No ranges — look for individual dates in a "upcoming dates" context
    lower = text.lower()
    for keyword in ("upcoming", "available", "schedule", "date", "start"):
        idx = lower.find(keyword)
        if idx == -1:
            continue
        snippet = text[max(0, idx - 20): idx + 400]
        for m in _SINGLE_DATE_RE.finditer(snippet):
            day, month, year = m.group(1), m.group(2), m.group(3)
            try:
                iso = dateutil_parser.parse(f"{day} {month} {year}").date().isoformat()
                results.append((iso, iso))
            except Exception:
                pass
        if results:
            return results

    return results


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class AsetAdapter(BaseAdapter):
    """Scraper adapter for ASET International Energy Training Academy
    (aset.co.uk).

    ASET offers GMDSS GOC and ROC courses.  The website currently displays
    no public schedule; the adapter fetches each course page to detect if a
    date calendar is added in future.  Until dates are present the adapter
    returns an empty list — no data is fabricated.

    robots.txt is absent (HTTP 404), so no crawling restrictions apply.
    A 2-second minimum delay is observed between requests to the domain.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        provider_id = provider.get("id", "unknown")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        first_request = True

        for course_id, path, duration_days, fallback_price in _COURSE_PAGES:
            url = BASE_URL + path

            if not first_request:
                time.sleep(_REQUEST_DELAY)
            first_request = False

            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("AsetAdapter: GET %s failed: %s", url, exc)
                continue

            try:
                soup = BeautifulSoup(resp.text, "lxml")
                page_text = soup.get_text(separator="\n")
            except Exception as exc:
                logger.warning("AsetAdapter: parse error for %s: %s", url, exc)
                continue

            # Extract price from page (use fallback if not found)
            price = _extract_price(page_text) or fallback_price

            # Attempt to find upcoming date sections
            date_pairs = _parse_date_ranges(page_text)

            if not date_pairs:
                logger.debug(
                    "AsetAdapter: no public dates found on %s for course %s",
                    url,
                    course_id,
                )
                # No fabricated offerings — skip
                continue

            for start_iso, end_iso in date_pairs:
                offering_id = (
                    f"{provider_id}-{_ADAPTER_SLUG}-{course_id}-{start_iso}"
                )
                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider_id,
                        start_date=start_iso,
                        end_date=end_iso,
                        timezone="Europe/London",
                        duration_days=duration_days,
                        price=price,
                        currency="GBP",
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(CONTACT_URL),
                        source_url=url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        logger.info(
            "AsetAdapter: %d offerings found for provider %s",
            len(offerings),
            provider_id,
        )
        return offerings
