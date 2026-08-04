"""Maritime Professional Training (MPT) USA adapter.

Scrapes https://www.mptusa.com/safety-training for STCW Basic Safety Training
class schedules.

Page structure (static HTML, no JS required):
  The schedule section contains multiple week-blocks.  Each week-block groups
  4 course entries.  Each entry uses a CSS-grid div (id="piotr-grid" in the
  DOM at time of writing) that holds:
    child 0 – course number text  (e.g. "141")
    child 1 – start date text     (e.g. "Mon 03 Aug 2026")
    child 2 – course name text    (e.g. "Personal Survival Techniques …")
    child 3 – div > p > <a href="/class-details/…/CLASS_ID">CLASS DETAILS</a>

  Because the page uses duplicate element IDs, BeautifulSoup's CSS selector
  `[id="piotr-grid"]` returns all of them.  We rely on the presence of a
  /class-details/ anchor rather than the ID alone.

Date format on the page: "Mon 03 Aug 2026"
Booking URL pattern:     https://school.mptusa.com/student/login.cfm?wishlist=CLASS_ID

All classes are at the Fort Lauderdale campus:
  1915 South Andrews Avenue, Fort Lauderdale, FL 33316

robots.txt: no restrictions on /safety-training; only /search-course?* is
disallowed for search bots.  Custom user-agent used throughout.
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

BASE_URL = "https://www.mptusa.com"
SAFETY_TRAINING_URL = f"{BASE_URL}/safety-training"
BOOKING_URL_TEMPLATE = "https://school.mptusa.com/student/login.cfm?wishlist={class_id}"

# Maps substrings found in class-details URL slugs to normalised course IDs.
# Checked in order – first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.technique|[/-]pst[/-]", re.I), "pst"),
    (re.compile(r"personal.safety.social|[/-]pssr[/-]", re.I), "pssr"),
    (re.compile(r"first.aid|[/-]cpr[/-]|[/-]efa[/-]", re.I), "efa"),
    (re.compile(r"fire.fight|[/-]fpff[/-]", re.I), "fpff"),
    (re.compile(r"survival.craft|[/-]pscrb[/-]", re.I), "pscrb"),
    (re.compile(r"advanced.fire|[/-]aff[/-]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[/-]mfa[/-]", re.I), "mfa"),
    (re.compile(r"medical.care|[/-]mc[/-]", re.I), "mc"),
    (re.compile(r"fast.rescue|[/-]frb[/-]", re.I), "frb"),
    (re.compile(r"basic.training.refresher|[/-]refresher[/-]", re.I), "pst"),
    (re.compile(r"basic.training.revalid|[/-]revalid[/-]", re.I), "pst"),
]

# "Mon 03 Aug 2026"  or  "3 Aug 2026"
_DATE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",
    re.I,
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Pattern to extract class ID from /class-details/<slug>/<id>
_CLASS_ID_RE = re.compile(r"/class-details/([^/]+)/(\d+)", re.I)


def _parse_date(text: str) -> str | None:
    """Parse 'Mon 03 Aug 2026' or '3 Aug 2026' -> '2026-08-03'. None on failure."""
    m = _DATE_RE.search(text.strip())
    if not m:
        return None
    day, month_abbr, year = m.group(1), m.group(2).lower()[:3], m.group(3)
    month = _MONTH_MAP.get(month_abbr)
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day)).date().isoformat()
    except ValueError:
        return None


def _course_id_from_slug(slug: str) -> str | None:
    """Return normalised course ID from a class-details URL slug."""
    padded = f"/{slug}/"
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class MptUsaAdapter(BaseAdapter):
    """Fetch STCW course offerings from mptusa.com."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Fetch the main STCW schedule page
        try:
            resp = session.get(SAFETY_TRAINING_URL, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("MPT USA: safety-training fetch failed: %s", e)
            return []
        time.sleep(2)

        try:
            offerings = self._parse_safety_training_page(
                resp.text, SAFETY_TRAINING_URL, provider
            )
        except Exception as e:
            logger.warning("MPT USA: safety-training parse failed: %s", e)
            return []

        logger.info("MPT USA adapter: %d offerings total", len(offerings))
        return offerings

    def _parse_safety_training_page(
        self, html: str, source_url: str, provider: dict
    ) -> list[Offering]:
        """Extract class offerings from the /safety-training schedule page.

        The page has no <table> elements; each class entry appears as a
        grid-div containing: course-number | start-date | course-name | link.
        We locate every anchor pointing to /class-details/ and walk upward
        to collect the sibling text nodes (date and course-name).
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=_CLASS_ID_RE):
            href: str = anchor["href"]
            m = _CLASS_ID_RE.search(href)
            if not m:
                continue
            slug, class_id = m.group(1), m.group(2)

            course_id = _course_id_from_slug(slug)
            if not course_id:
                logger.debug("MPT USA: no course_id for slug %r", slug)
                continue

            # Walk up to the containing grid div (holds course#, date, name, link)
            grid_div = anchor.parent  # <p>
            if grid_div:
                grid_div = grid_div.parent  # <div id="flexing">
            if grid_div:
                grid_div = grid_div.parent  # the grid row div

            start_date: str | None = None
            if grid_div:
                # Get all direct text / child text in the grid row
                full_text = grid_div.get_text(" ", strip=True)
                start_date = _parse_date(full_text)

            if not start_date:
                logger.debug(
                    "MPT USA: no date found for class_id=%s slug=%s", class_id, slug
                )
                continue

            # Deduplicate by (course_id, start_date)
            dedup_key = f"{course_id}-{start_date}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            booking_url = safe_url(
                BOOKING_URL_TEMPLATE.format(class_id=class_id)
            )
            class_url = safe_url(
                f"{BASE_URL}/class-details/{slug}/{class_id}"
            )

            offerings.append(
                Offering(
                    id=f"{course_id}-mpt-usa-{start_date}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=start_date,
                    timezone="America/New_York",
                    duration_days=None,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=booking_url,
                    source_url=class_url or source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
