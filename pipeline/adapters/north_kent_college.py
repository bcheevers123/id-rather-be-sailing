"""North Kent College (northkent.ac.uk) — National Maritime Training Centre adapter.

Scrapes individual STCW course pages on www.northkent.ac.uk for upcoming dates.

Site structure (per page):
  - Each course page under /courses/national-maritime-training-centre/<slug>
  - A course-detail table shows "Starting DD/MM/YYYY" and "Ending DD/MM/YYYY"
  - Price is shown as "Course cost from £NNN.00" in an accordion section
  - A "Dates available" link points to the college store at /store/...
  - Only one upcoming date is shown per page (not a full schedule list)

robots.txt check (2026-08-04):
  - Only system directories (/administrator/, /bin/, etc.) are Disallowed
  - General scraping of course pages is permitted

NOTE: This is DISTINCT from pipeline/adapters/north_kent.py which targets
nmtctraining.co.uk (the NMTC-branded sub-site).  This adapter targets the
parent college site northkent.ac.uk which duplicates some course pages with
different booking URLs into the college store.
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

BASE_URL = "https://www.northkent.ac.uk"
NMTC_PATH = "/courses/national-maritime-training-centre"

# STCW course page slugs to scrape (derived from sitemap 2026-08-04).
# Each tuple is (slug, course_id).
_STCW_COURSE_SLUGS: list[tuple[str, str]] = [
    ("stcw-elementary-first-aid-commercial-gravesend", "efa"),
    ("stcw-personal-safety-social-responsibilities-commercial-gravesend", "pssr"),
    ("stcw-personal-survival-techniques-commercial-gravesend", "pst"),
    ("stcw-proficiency-in-fast-rescue-boats-commercial-gravesend", "frb"),
    ("stcw-proficiency-in-security-awareness-commercial-gravesend", "pssr"),
    ("stcw-proficiency-in-survival-craft-rescue-boats-commercial-gravesend", "pscrb"),
    ("stcw-advanced-fire-fighting-commercial-gravesend", "aff"),
    ("stcw-proficiency-in-medical-first-aid-commercial-gravesend", "mfa"),
    ("stcw-basic-safety-training-week-commercial-gravesend", "pst"),
    # Updating training variants
    (
        "stcw-advanced-fire-fighting-updating-training-full-day-commercial-gravesend",
        "aff",
    ),
    (
        "stcw-advanced-fire-fighting-updating-training-half-day-commercial-gravesend",
        "aff",
    ),
    (
        "stcw-proficiency-in-fast-rescue-boats-updating-training-full-day-commercial-gravesend",
        "frb",
    ),
    (
        "stcw-proficiency-in-fast-rescue-boats-updating-training-half-day-commercial-gravesend",
        "frb",
    ),
    (
        "stcw-proficiency-in-survival-craft-rescue-boats-updating-training-half-day-commercial-gravesend",
        "pscrb",
    ),
]

# Regex patterns for scraping page text
_START_DATE_RE = re.compile(r"Starting\s+(\d{1,2}/\d{2}/\d{4})", re.I)
_END_DATE_RE = re.compile(r"Ending\s+(\d{1,2}/\d{2}/\d{4})", re.I)
_PRICE_RE = re.compile(r"Course cost from\s*£([\d,]+)(?:\.(\d{2}))?", re.I)


def _parse_dmY(date_str: str) -> str | None:
    """Convert DD/MM/YYYY to YYYY-MM-DD, or return None on failure."""
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _extract_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        integer_part = m.group(1).replace(",", "")
        decimal_part = m.group(2) or "0"
        return float(f"{integer_part}.{decimal_part}")
    except (ValueError, AttributeError):
        return None


def _extract_store_url(soup: BeautifulSoup) -> str | None:
    """Return the first /store/ link on the page, or None."""
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if "/store/" in href:
            if href.startswith("http"):
                return href
            return BASE_URL + href
    return None


class NorthKentCollegeAdapter(BaseAdapter):
    """Adapter for National Maritime Training Centre pages on northkent.ac.uk."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []

        for slug, course_id in _STCW_COURSE_SLUGS:
            url = f"{BASE_URL}{NMTC_PATH}/{slug}"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(
                    "NorthKentCollege: fetch failed for %s: %s", url, e
                )
                time.sleep(2)
                continue

            time.sleep(2)  # Polite 2-second delay between requests

            try:
                offering = self._parse_course_page(
                    resp.text, url, course_id, provider
                )
                if offering:
                    all_offerings.append(offering)
            except Exception as e:
                logger.warning(
                    "NorthKentCollege: parse failed for %s: %s", url, e
                )

        logger.info(
            "NorthKentCollege adapter: %d offerings for provider %s",
            len(all_offerings),
            provider.get("id"),
        )
        return all_offerings

    def _parse_course_page(
        self,
        html: str,
        page_url: str,
        course_id: str,
        provider: dict,
    ) -> Offering | None:
        """Parse a single course page; return Offering or None if no date found."""
        soup = BeautifulSoup(html, "lxml")
        page_text = soup.get_text(" ", strip=True)

        # Extract start and end dates
        start_match = _START_DATE_RE.search(page_text)
        end_match = _END_DATE_RE.search(page_text)

        if not start_match:
            logger.debug("NorthKentCollege: no date found on %s", page_url)
            return None

        start_iso = _parse_dmY(start_match.group(1))
        if not start_iso:
            logger.debug(
                "NorthKentCollege: could not parse start date on %s", page_url
            )
            return None

        end_iso = _parse_dmY(end_match.group(1)) if end_match else start_iso

        # Extract price
        price = _extract_price(page_text)

        # Extract booking URL from /store/ link
        store_url = _extract_store_url(soup)
        booking_url = safe_url(store_url)

        now = datetime.now(timezone.utc).isoformat()
        provider_id = provider["id"]
        offering_id = f"{course_id}-nmtc-{start_iso}"

        return Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider_id,
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
