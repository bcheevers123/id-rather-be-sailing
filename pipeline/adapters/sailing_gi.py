"""Allabroad Maritime Academy (sailing.gi) adapter.

Scrapes individual MCA STCW course pages on www.sailing.gi to find upcoming
course start dates.  Dates are published as static HTML list items under a
"Schedule / Dates" heading in the format "DD Mon" (e.g. "27 Jul", "7 Sept").

Course pages discovered from the MCA STCW sitemap:
  https://www.sailing.gi/mca-stcw-course-sitemap.xml
"""
import logging
import re
import time
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.sailing.gi"

# Known STCW course pages with their normalised course IDs and duration (days).
# Pages that have no reliable fixed dates (AFF, MFA, EDH, AEC1) are included
# but will yield zero offerings when dates are "TBA".
_COURSE_PAGES: list[dict] = [
    {
        "url": f"{BASE_URL}/mca-stcw-courses/stcw-basic-safety-training/",
        "course_id": "pst",        # BST bundle; primary STCW product
        "duration_days": 5,
        "price": 995.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/mca-stcw-personal-survival-techniques/",
        "course_id": "pst",
        "duration_days": 1,
        "price": 175.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/stcw-fire-prevention-and-fire-fighting/",
        "course_id": "fpff",
        "duration_days": 2,
        "price": None,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/stcw-personal-safety-and-social-responsibilities/",
        "course_id": "pssr",
        "duration_days": 1,
        "price": 110.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/mca-stcw-elementary-first-aid/",
        "course_id": "efa",
        "duration_days": 1,
        "price": 135.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/stcw-course-update/",
        "course_id": "pst",        # STCW Update (refresher)
        "duration_days": 2,
        "price": 570.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/advanced-fire-fighting-mca/",
        "course_id": "aff",
        "duration_days": 4,
        "price": 950.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/mca-stcw-medical-first-aid/",
        "course_id": "mfa",
        "duration_days": 4,
        "price": 595.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/mca-stcw-efficient-deck-hand/",
        "course_id": "mc",         # Closest match: maritime competence / EDH
        "duration_days": 5,
        "price": 775.0,
    },
    {
        "url": f"{BASE_URL}/mca-stcw-courses/mca-approved-engine-course/",
        "course_id": "mc",
        "duration_days": 5,
        "price": 950.0,
    },
]

# Matches "DD Mon" variants: "27 Jul", "7 Sept", "14 Dec", etc.
# Also handles fully spelled-out "27 July" or "14 September".
_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\b",
    re.IGNORECASE,
)

# Full date pattern: "14 September 2026" or "14 Sept 2026"
_FULL_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
    r"\s+(\d{4})\b",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_month(raw: str) -> int:
    """Convert a month abbreviation/name to integer 1-12."""
    key = raw[:3].lower()
    return _MONTH_MAP[key]


def _infer_year(day: int, month: int, reference: date) -> int:
    """Given a day/month without a year, infer the most likely upcoming year.

    If the month/day is in the past relative to *reference*, assume next year.
    """
    for yr in (reference.year, reference.year + 1):
        try:
            d = date(yr, month, day)
        except ValueError:
            continue
        if d >= reference:
            return yr
    return reference.year + 1


def _extract_dates_from_page(html: str, source_url: str) -> list[str]:
    """Return ISO date strings extracted from the schedule section of a page.

    Strategy:
    1. Find a heading whose text contains "schedule" or "dates".
    2. Walk the sibling/child <ul> or <li> elements after that heading.
    3. Parse each li text for a "DD Mon" or "DD Month YYYY" pattern.

    Falls back to scanning all <li> elements page-wide if the heading is
    not found.
    """
    soup = BeautifulSoup(html, "lxml")
    today = date.today()

    # Locate the schedule heading
    schedule_heading = None
    for tag in soup.find_all(re.compile(r"^h[2-4]$")):
        if re.search(r"schedule|dates?", tag.get_text(), re.IGNORECASE):
            schedule_heading = tag
            break

    candidate_items: list[str] = []

    if schedule_heading:
        # Collect text from <li> elements that follow the heading (same parent or next sibling ul)
        node = schedule_heading.find_next_sibling()
        while node:
            if node.name in ("h2", "h3", "h4", "h5"):
                break  # stop at next heading
            if node.name == "ul":
                for li in node.find_all("li"):
                    candidate_items.append(li.get_text(" ", strip=True))
            elif node.name == "li":
                candidate_items.append(node.get_text(" ", strip=True))
            node = node.find_next_sibling()

    # Fallback: scan all <li> site-wide
    if not candidate_items:
        for li in soup.find_all("li"):
            candidate_items.append(li.get_text(" ", strip=True))

    iso_dates: list[str] = []
    seen: set[str] = set()

    for text in candidate_items:
        # Try full date with year first
        m_full = _FULL_DATE_RE.search(text)
        if m_full:
            try:
                day = int(m_full.group(1))
                month = _parse_month(m_full.group(2))
                year = int(m_full.group(3))
                iso = date(year, month, day).isoformat()
                if iso not in seen:
                    seen.add(iso)
                    iso_dates.append(iso)
                continue
            except (ValueError, KeyError):
                pass

        # Try "DD Mon" without year
        m = _DATE_RE.search(text)
        if m:
            try:
                day = int(m.group(1))
                month = _parse_month(m.group(2))
                year = _infer_year(day, month, today)
                iso = date(year, month, day).isoformat()
                if iso not in seen:
                    seen.add(iso)
                    iso_dates.append(iso)
            except (ValueError, KeyError):
                pass

    return iso_dates


class SailingGiAdapter(BaseAdapter):
    """Fetch STCW course offerings from Allabroad Maritime Academy, Gibraltar."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for course_meta in _COURSE_PAGES:
            url = course_meta["url"]
            course_id: str = course_meta["course_id"]
            duration_days: float | None = course_meta.get("duration_days")
            price: float | None = course_meta.get("price")

            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("sailing.gi fetch failed %s: %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                iso_dates = _extract_dates_from_page(resp.text, url)
            except Exception as exc:
                logger.warning("sailing.gi parse failed %s: %s", url, exc)
                continue

            for iso in iso_dates:
                # Compute end_date from duration
                if duration_days is not None:
                    try:
                        start = date.fromisoformat(iso)
                        end_iso = (
                            date(start.year, start.month, start.day)
                            .__class__.fromordinal(
                                start.toordinal() + int(duration_days) - 1
                            )
                            .isoformat()
                        )
                    except Exception:
                        end_iso = iso
                else:
                    end_iso = iso

                offering_id = f"{course_id}-sailing-gi-{iso}-{url.rstrip('/').split('/')[-1]}"

                all_offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=iso,
                        end_date=end_iso,
                        timezone="Europe/Gibraltar",
                        duration_days=duration_days,
                        price=price,
                        currency="GBP",
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(url),
                        source_url=url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

            logger.info(
                "sailing.gi: %d dates for course_id=%s (%s)",
                len(iso_dates),
                course_id,
                url,
            )

        logger.info("sailing.gi adapter: %d total offerings", len(all_offerings))
        return all_offerings
