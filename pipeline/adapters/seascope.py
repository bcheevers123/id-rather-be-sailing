"""Seascope Maritime Training adapter.

Scrapes https://seascopemaritimetraining.com/courses/ to discover course pages,
then visits each STCW-relevant course page and parses the schedule table:

    Location    Start              End
    Palma       31 May 2026        04 June 2026
    Antibes     23 August 2026     27 August 2026

Each table row becomes one Offering.  No price information is published on the
site, so price is always None.
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
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://seascopemaritimetraining.com"
LISTING_URL = "https://seascopemaritimetraining.com/courses/"

# Keywords in slug / title -> canonical course_id.
# Evaluated in order; first match wins.
_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpst\b|personal.survival", re.I), "pst"),
    (re.compile(r"\bfpff\b|fire.prevention|fire.fighting", re.I), "fpff"),
    (re.compile(r"\befa\b|elementary.first.aid", re.I), "efa"),
    (re.compile(r"\bpssr\b|personal.safety.and.social", re.I), "pssr"),
    (re.compile(r"\bpscrb\b|survival.craft", re.I), "pscrb"),
    (re.compile(r"\baff\b|advanced.fire", re.I), "aff"),
    (re.compile(r"\bmfa\b|medical.first.aid", re.I), "mfa"),
]


def _identify_course(slug: str, title: str) -> str | None:
    """Return canonical course_id or None if the page is not an STCW course."""
    text = f"{slug} {title}"
    for pattern, course_id in _COURSE_MAP:
        if pattern.search(text):
            return course_id
    return None


def _location_slug(location: str) -> str:
    """Convert a location name to a URL-safe slug (lowercase, hyphens)."""
    return re.sub(r"[^a-z0-9]+", "-", location.strip().lower()).strip("-")


class SeascopeAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # --- Step 1: discover course page URLs ---
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Seascope listing fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            course_urls = _extract_course_urls(resp.text)
        except Exception as exc:
            logger.warning("Seascope listing parse failed: %s", exc)
            return []

        if not course_urls:
            logger.warning("Seascope: no course URLs found on listing page")
            return []

        # --- Step 2: scrape each course page ---
        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for url in course_urls:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Seascope course fetch failed %s: %s", url, exc)
                time.sleep(2)
                continue

            time.sleep(2)

            try:
                offerings = _parse_course_page(resp.text, url, provider, now)
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning("Seascope course parse failed %s: %s", url, exc)
                continue

        logger.info(
            "Seascope adapter extracted %d offerings across %d course pages",
            len(all_offerings),
            len(course_urls),
        )
        return all_offerings


def _extract_course_urls(html: str) -> list[str]:
    """Return unique absolute course page URLs from the listing page."""
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    urls: list[str] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        # Must be under /courses/ and not the listing page itself
        if "/courses/" not in href:
            continue
        absolute = urljoin(BASE_URL, href).rstrip("/")
        listing = LISTING_URL.rstrip("/")
        if absolute == listing:
            continue
        # Ignore anchor-only or mailto links
        if not absolute.startswith("http"):
            continue
        if absolute not in seen:
            seen.add(absolute)
            urls.append(absolute)

    return urls


def _parse_course_page(
    html: str,
    url: str,
    provider: dict,
    now: str,
) -> list[Offering]:
    """Parse a single course page and return Offering objects."""
    soup = BeautifulSoup(html, "lxml")

    # Derive slug from URL path for course identification
    path = url.split("seascopemaritimetraining.com")[-1]
    slug = path.strip("/").split("/")[-1]

    # Also grab page title for identification
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    course_id = _identify_course(slug, title)
    if course_id is None:
        logger.debug("Seascope: skipping non-STCW page %s", url)
        return []

    offerings: list[Offering] = []
    seen: set[str] = set()

    # Find a table whose headers include Location / Start / End (case-insensitive)
    schedule_table = _find_schedule_table(soup)
    if schedule_table is None:
        logger.debug("Seascope: no schedule table found on %s", url)
        return []

    rows = schedule_table.find_all("tr")
    for row in rows:
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if len(cells) < 3:
            continue

        # Skip header rows
        row_text = " ".join(cells).lower()
        if "location" in row_text and "start" in row_text:
            continue

        location_raw, start_raw, end_raw = cells[0], cells[1], cells[2]

        if not location_raw or not start_raw or not end_raw:
            continue

        try:
            start_d = dateutil_parser.parse(start_raw, fuzzy=True).date().isoformat()
            end_d = dateutil_parser.parse(end_raw, fuzzy=True).date().isoformat()
        except Exception:
            logger.debug(
                "Seascope: could not parse dates '%s' / '%s' on %s",
                start_raw, end_raw, url,
            )
            continue

        loc_slug = _location_slug(location_raw)
        offering_id = f"{course_id}-seascope-{loc_slug}-{start_d}"

        if offering_id in seen:
            continue
        seen.add(offering_id)

        offerings.append(Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider["id"],
            start_date=start_d,
            end_date=end_d,
            timezone="Europe/London",
            duration_days=None,
            price=None,
            currency=None,
            vat_included=None,
            delivery_format="in_person",
            availability=location_raw,
            booking_url=safe_url(url),
            source_url=url,
            last_verified=now,
            freshness_status="verified",
        ))

    return offerings


def _find_schedule_table(soup: BeautifulSoup):
    """Return the first table that looks like a Location/Start/End schedule."""
    for table in soup.find_all("table"):
        text = table.get_text(" ", strip=True).lower()
        if "location" in text and ("start" in text or "date" in text):
            return table

    # Fallback: any table with 3+ columns where the first row has date-like content
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        first_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
        if len(first_cells) >= 3:
            return table

    return None
