"""Humberside Offshore Training Association (HOTA) adapter.

Scrapes the HOTA maritime training course listing page to discover individual
course pages, then scrapes each course page for its availability table.

Availability table format (DD/MM/YYYY dates, integer spaces):
    Event Date    Available Spaces    Book
    10/08/2026    8
    07/09/2026    12
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

BASE_URL = "https://www.hota.org"
LISTING_URL = f"{BASE_URL}/training-courses/maritime-training-courses.aspx"

# Maps keywords found in course page titles / URLs to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
]

# DD/MM/YYYY date pattern
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# "8 spaces" or just "8" in the availability cell
_SPACES_RE = re.compile(r"(\d+)")


def _course_id_from_text(text: str) -> str | None:
    """Return a course ID by matching text against the keyword map."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class HotaAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: fetch the course listing page
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("HOTA listing fetch failed: %s", e)
            return []
        time.sleep(2)

        # Step 2: extract links to individual course pages
        try:
            course_links = self._extract_course_links(resp.text)
        except Exception as e:
            logger.warning("HOTA listing parse failed: %s", e)
            return []

        if not course_links:
            logger.warning("HOTA: no course links found on listing page")
            return []

        # Step 3: scrape each course page
        all_offerings: list[Offering] = []
        for url in course_links:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("HOTA course fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_course_page(resp.text, url, provider)
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("HOTA course parse failed %s: %s", url, e)

        logger.info("HOTA adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _extract_course_links(self, html: str) -> list[str]:
        """Return absolute URLs of individual maritime course pages."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            # Course pages live under /training-courses/maritime-training-courses/
            if "/training-courses/maritime-training-courses/" not in href.lower():
                continue
            # Skip the listing page itself
            if href.lower().rstrip("/").endswith("maritime-training-courses"):
                continue
            # Build absolute URL
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE_URL + href
            else:
                abs_url = BASE_URL + "/" + href
            if abs_url not in seen:
                seen.add(abs_url)
                links.append(abs_url)

        return links

    def _parse_course_page(
        self, html: str, page_url: str, provider: dict
    ) -> list[Offering]:
        """Parse availability table rows from a single HOTA course page."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course ID from page title or URL
        title_tag = soup.find("h1") or soup.find("title")
        title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
        course_id = _course_id_from_text(title_text) or _course_id_from_text(page_url)
        if not course_id:
            logger.debug("HOTA: could not determine course_id for %s", page_url)
            return []

        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        # Look for table rows containing DD/MM/YYYY dates
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Scan cells for a date
            start_date_iso: str | None = None
            availability: str | None = None

            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                m = _DATE_RE.search(cell_text)
                if m and start_date_iso is None:
                    try:
                        d = datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
                    except ValueError:
                        continue
                    start_date_iso = d
                    # The next cell(s) may hold available spaces
                    if i + 1 < len(cells):
                        next_text = cells[i + 1].get_text(strip=True)
                        sm = _SPACES_RE.search(next_text)
                        if sm:
                            availability = f"{sm.group(1)} spaces"

            if not start_date_iso or start_date_iso in seen_dates:
                continue
            seen_dates.add(start_date_iso)

            offerings.append(
                Offering(
                    id=f"{course_id}-hota-{start_date_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date_iso,
                    end_date=start_date_iso,
                    timezone="Europe/London",
                    duration_days=None,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=safe_url(page_url),
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "HOTA: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
