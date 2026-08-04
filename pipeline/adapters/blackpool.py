"""Adapter for Blackpool and The Fylde College — Fleetwood Nautical Campus.

Scrapes the STCW course listing page and each individual course page for dates
and prices. No booking URL is available (only mailto links); booking_url is set
to None for all offerings.
"""
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

STCW_COURSE_PAGE = "https://fleetwoodnautical.blackpool.ac.uk/courses/offshore-stcw-courses"
BASE_URL = "https://fleetwoodnautical.blackpool.ac.uk"

# Map substrings found in course titles/names to MCA course_ids.
# Checked against the longest/most specific match first.
_COURSE_NAME_MAP: list[tuple[str, str]] = [
    # More specific entries must come before substrings that would match them.
    ("Basic Safety Training", "bst"),
    ("Basic Safety", "bst"),
    ("Personal Survival Techniques", "pst"),
    ("Personal Survival", "pst"),
    ("Advanced Fire Fighting", "aff"),
    ("AFF", "aff"),
    ("Fire Prevention and Fire Fighting", "fpff"),
    ("Fire Prevention", "fpff"),
    # "Fire Fighting" alone must come after "Advanced Fire Fighting" and "Fire Prevention..."
    ("Fire Fighting", "fpff"),
    ("Elementary First Aid", "efa"),
    ("Personal Safety and Social Responsibilit", "pssr"),
    ("Personal Safety", "pssr"),
    ("PSSR", "pssr"),
    ("Proficiency in Survival Craft and Rescue Boats", "pscrb"),
    ("Survival Craft", "pscrb"),
    ("PSCRB", "pscrb"),
    ("Fast Rescue Boat", "frb"),
    ("FRB", "frb"),
    # Medical First Aid must come before the bare "First Aid" catch-all for EFA.
    ("Proficiency in Medical First Aid", "mfa"),
    ("Medical First Aid", "mfa"),
    ("Proficiency in Medical Care", "mc"),
    ("Medical Care", "mc"),
    # Bare "First Aid" catch-all — only reached if none of the above matched.
    ("First Aid", "efa"),
]

# Regex to extract price from strings like "2 Days/ £420" or "1 Week/ £1,340"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")

# Regex for date strings like "15 Sep 2026" or "30 Nov 2026"
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")

# Regex for course path links — offshore STCW courses use oe1ec prefix
_COURSE_LINK_RE = re.compile(r"^/course/oe1ec", re.I)


def _map_course_name(title: str) -> str | None:
    """Return the MCA course_id for the given course title, or None if unknown."""
    for substring, course_id in _COURSE_NAME_MAP:
        if substring.lower() in title.lower():
            return course_id
    return None


def _extract_price(text: str) -> float | None:
    """Extract a GBP price from a duration/fee string like '1 Week/ £1,340'."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class BlackpoolAdapter(BaseAdapter):
    """Scrapes STCW course dates from Fleetwood Nautical Campus."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        offerings: list[Offering] = []

        # 1. Fetch the listing page to discover individual course URLs.
        try:
            resp = session.get(STCW_COURSE_PAGE, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Blackpool listing fetch failed: %s", e)
            return []
        time.sleep(2)

        course_urls = _extract_course_links(resp.text)
        logger.info("Blackpool: found %d course links on listing page", len(course_urls))

        # 2. Fetch each course page and parse dates/prices.
        for url in course_urls:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Blackpool course fetch failed for %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                page_offerings = _parse_course_page(resp.text, url, provider)
            except Exception as e:
                logger.warning("Blackpool parse failed for %s: %s", url, e)
                continue

            offerings.extend(page_offerings)

        logger.info("Blackpool adapter extracted %d offerings total", len(offerings))
        return offerings


def _extract_course_links(html: str) -> list[str]:
    """Return absolute course page URLs from the listing page."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    urls: list[str] = []
    for a in soup.find_all("a", href=_COURSE_LINK_RE):
        href = a["href"]
        absolute = urljoin(BASE_URL, href)
        if absolute not in seen:
            seen.add(absolute)
            urls.append(absolute)
    return urls


def _parse_course_page(html: str, source_url: str, provider: dict) -> list[Offering]:
    """Parse a single Blackpool course page and return Offering objects."""
    soup = BeautifulSoup(html, "lxml")
    offerings: list[Offering] = []
    now = datetime.now(timezone.utc).isoformat()

    # Derive course name from the mailto subject line or from <title>.
    course_name = _extract_course_name(soup)
    course_id = _map_course_name(course_name) if course_name else None
    if not course_id:
        logger.debug("Blackpool: no course_id mapping for %r at %s — skipping", course_name, source_url)
        return []

    # Find the date table inside #course-content / #occ.
    occ_div = soup.find(id="occ") or soup.find(id="course-content")
    if occ_div is None:
        occ_div = soup

    seen_dates: set[str] = set()
    for row in occ_div.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        # First cell with a date string is the start date.
        date_str = None
        for cell in cells:
            text = cell.get_text(strip=True)
            m = _DATE_RE.search(text)
            if m:
                try:
                    date_str = dateutil_parser.parse(m.group(), fuzzy=False).date().isoformat()
                except Exception:
                    continue
                break

        if not date_str or date_str in seen_dates:
            continue
        seen_dates.add(date_str)

        # Extract price from the duration/fee cell (typically the 3rd cell).
        price: float | None = None
        for cell in cells:
            candidate = _extract_price(cell.get_text(strip=True))
            if candidate is not None:
                price = candidate
                break

        offerings.append(Offering(
            id=f"{course_id}-blackpool-{date_str}",
            course_id=course_id,
            provider_id=provider["id"],
            start_date=date_str,
            end_date=date_str,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=None,
            booking_url=None,  # only mailto available
            source_url=source_url,
            last_verified=now,
            freshness_status="verified",
        ))

    return offerings


def _extract_course_name(soup: BeautifulSoup) -> str | None:
    """Extract course name from mailto subject or page title."""
    # Try the mailto href first — most reliable source.
    for a in soup.find_all("a", href=re.compile(r"mailto:", re.I)):
        href = a.get("href", "")
        m = re.search(r"subject=Course Enquiry:\s*(.+?)(?:&|$)", href, re.I)
        if m:
            return m.group(1).strip()

    # Fall back to <title> tag, stripping the site suffix.
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Strip common suffixes like "| Fleetwood Nautical Campus"
        for sep in [" | ", " - ", " – "]:
            if sep in title:
                return title.split(sep)[0].strip()
        return title.strip()

    return None
