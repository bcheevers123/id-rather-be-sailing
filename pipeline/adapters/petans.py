"""Petans Limited adapter.

Scrapes the maritime course listing at https://www.petans.co.uk/courses/maritime/,
then fetches each individual course page to extract scheduled dates, places, and price.
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

BASE = "https://www.petans.co.uk"
LISTING_URL = "https://www.petans.co.uk/courses/maritime/"

_PRICE_RE = re.compile(r"[£\xA3]([\d,]+(?:\.\d{2})?)")

# "06 Aug 2026 - 06 Aug 2026"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s*[-–]\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"
)
_DATE_SINGLE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})")

# Ordered list: (course_id, [keywords to match in lowercase url+title])
# More-specific terms first to avoid partial-match collisions.
_COURSE_ID_MAP: list[tuple[str, list[str]]] = [
    ("pscrb", ["pscrb", "survival craft", "survival-craft"]),
    ("fpff",  ["fpff",  "fire prevention", "fire-prevention"]),
    ("pssr",  ["pssr",  "personal safety", "personal-safety"]),
    ("pst",   ["pst",   "basic safety",    "basic-safety"]),
    ("efa",   ["efa"]),
    ("aff",   ["aff",   "advanced fire",   "advanced-fire"]),
    ("mfa",   ["mfa",   "medical first aid", "medical-first-aid"]),
]


def _resolve_course_id(url: str, title: str) -> str | None:
    """Return a canonical course_id by matching keywords against the URL path and title."""
    haystack = (url + " " + title).lower()
    for course_id, keywords in _COURSE_ID_MAP:
        for kw in keywords:
            if kw in haystack:
                return course_id
    return None


class PetansAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            course_urls = self._get_course_links(session)
        except Exception as exc:
            logger.warning("Petans: listing page failed: %s", exc)
            return []

        offerings: list[Offering] = []
        for url in course_urls:
            time.sleep(2)
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Petans: fetch failed for %s: %s", url, exc)
                continue
            try:
                offerings.extend(self._parse_course_page(resp.text, url, provider))
            except Exception as exc:
                logger.warning("Petans: parse failed for %s: %s", url, exc)

        logger.info("Petans adapter: %d offerings total", len(offerings))
        return offerings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_course_links(self, session: requests.Session) -> list[str]:
        resp = session.get(LISTING_URL, timeout=20)
        resp.raise_for_status()
        time.sleep(2)

        soup = BeautifulSoup(resp.text, "lxml")
        seen: set[str] = set()
        links: list[str] = []

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            # Normalise to absolute URL
            if href.startswith("/"):
                href = BASE + href
            # Drop anchors, query strings, and external domains
            href = href.split("?")[0].split("#")[0]
            if "petans.co.uk" not in href:
                continue
            # Must be at least two path levels deep under /courses/
            if not re.search(r"/courses/[^/]+/[^/]", href):
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(href)

        logger.debug("Petans: found %d candidate course URLs from listing", len(links))
        return links

    def _parse_course_page(
        self, html: str, url: str, provider: dict
    ) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Resolve course_id from URL + page <h1>
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        course_id = _resolve_course_id(url, title)
        if not course_id:
            logger.debug("Petans: no course_id for %s (%r), skipping", url, title)
            return []

        # Price — shown as exc. VAT so vat_included is always False
        price: float | None = None
        pm = _PRICE_RE.search(soup.get_text())
        if pm:
            try:
                price = float(pm.group(1).replace(",", ""))
            except ValueError:
                pass

        offerings: list[Offering] = []
        seen_starts: set[str] = set()

        for row in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if not cells:
                continue

            date_text = cells[0]
            range_m = _DATE_RANGE_RE.search(date_text)
            if range_m:
                start_str, end_str = range_m.group(1), range_m.group(2)
            else:
                single_m = _DATE_SINGLE_RE.search(date_text)
                if not single_m:
                    continue
                start_str = end_str = single_m.group(1)

            try:
                start_d = dateutil_parser.parse(start_str, fuzzy=False).date().isoformat()
                end_d   = dateutil_parser.parse(end_str,   fuzzy=False).date().isoformat()
            except Exception:
                continue

            if start_d in seen_starts:
                continue
            seen_starts.add(start_d)

            # Places: second column
            availability: str | None = None
            if len(cells) > 1:
                places = cells[1].strip()
                if places:
                    availability = f"{places} places" if places.isdigit() else places

            offerings.append(Offering(
                id=f"{course_id}-petans-{start_d}",
                course_id=course_id,
                provider_id=provider["id"],
                start_date=start_d,
                end_date=end_d,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP",
                vat_included=False,
                delivery_format="in_person",
                availability=availability,
                booking_url=safe_url(url),
                source_url=url,
                last_verified=now,
                freshness_status="verified",
            ))

        logger.info("Petans: %d offerings from %s", len(offerings), url)
        return offerings
