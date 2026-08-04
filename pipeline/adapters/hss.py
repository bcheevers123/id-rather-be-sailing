"""JPMA & Hoylake Sailing School (HSS) adapter.

Scrapes the static course-dates page at https://www.hss.ac.uk/course-dates/
which lists upcoming course runs as plain bullet-point text (no tables, no JS).

The site offers only two STCW-relevant courses:
  - EFA  : "1 Day First Aid" (RYA Small Craft / MCA STCW Elementary First Aid)
  - MFA  : "Medical First Aid Aboard Ship (STCW)"

Both regularly show "Dates TBC – contact school to register interest", so
live offerings may be zero on any given fetch.  The adapter also scans the
course-details pages for EFA and MFA in case dated runs are ever published
there.

Date formats found on the page (examples):
  "3rd – 7th August 2026"
  "1 Sept 2026 – 5 Sept 2026"
  "28th Sept – 9th Oct 2026"

robots.txt: Disallow /wp-admin/ only — all public pages are permitted.
Booking: no online system; contact reception@hss.ac.uk / +44 151 632 4000.
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

BASE_URL = "https://www.hss.ac.uk"
COURSE_DATES_URL = f"{BASE_URL}/course-dates/"

# Individual course detail pages that may also list dated runs
_COURSE_DETAIL_PAGES: dict[str, str] = {
    "efa": f"{BASE_URL}/course-details/first-aid-courses/basic-first-aid/",
    "mfa": f"{BASE_URL}/course-details/first-aid-courses/medical-first-aid-aboard-ship/",
}

# Maps section headings / course title text -> course_id
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]|1.day.first.aid", re.I), "efa"),
    (re.compile(r"medical.*(?:first.aid|\baid\b.*ship)|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.*fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.*social.responsibility|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(
        r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I
    ), "pscrb"),
    (re.compile(r"advanced.fire.?fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.care|[^a-z]\bmc\b[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# Month name -> zero-padded month number
_MONTHS: dict[str, str] = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

# Ordinal suffixes
_ORDINAL_RE = re.compile(r"(\d+)(?:st|nd|rd|th)", re.I)

# Duration hints for known courses (days)
_DURATION: dict[str, float] = {
    "efa": 1.0,
    "mfa": 4.0,
    "pst": 1.0,
    "fpff": 1.0,
    "pssr": 0.5,
    "pscrb": 2.0,
    "aff": 2.0,
    "mc": 5.0,
    "frb": 1.0,
}


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _strip_ordinals(text: str) -> str:
    """Remove ordinal suffixes: '3rd' -> '3', '21st' -> '21'."""
    return _ORDINAL_RE.sub(r"\1", text)


def _parse_date_range(text: str) -> tuple[str | None, str | None]:
    """
    Parse a date-range string like:
        "3 – 7 August 2026"
        "28 Sept – 9 Oct 2026"
        "1 Sept 2026 – 5 Sept 2026"
        "7 – 11 September 2026"
        "6 July 2026"          (single date)

    Returns (start_iso, end_iso) or (None, None) on failure.
    """
    text = _strip_ordinals(text).strip()

    # Replace en-dash / em-dash with hyphen for uniform splitting
    text = re.sub(r"[–—]", "-", text)

    # Try "DD - DD Month YYYY" (same month, no month on first part)
    m = re.match(
        r"^(\d{1,2})\s*-\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$",
        text,
    )
    if m:
        d1, d2, mon, yr = m.groups()
        mon_num = _MONTHS.get(mon[:3].lower())
        if mon_num:
            start = f"{yr}-{mon_num}-{d1.zfill(2)}"
            end = f"{yr}-{mon_num}-{d2.zfill(2)}"
            return start, end

    # Try "DD Month - DD Month YYYY" or "DD Month YYYY - DD Month YYYY"
    m = re.match(
        r"^(\d{1,2})\s+([A-Za-z]+)\s*(?:(\d{4})\s*)?-\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$",
        text,
    )
    if m:
        d1, mon1, yr1, d2, mon2, yr2 = m.groups()
        mon1_num = _MONTHS.get(mon1[:3].lower())
        mon2_num = _MONTHS.get(mon2[:3].lower())
        if mon1_num and mon2_num:
            start = f"{yr1 or yr2}-{mon1_num}-{d1.zfill(2)}"
            end = f"{yr2}-{mon2_num}-{d2.zfill(2)}"
            return start, end

    # Single date: "DD Month YYYY" or "DD Month" (year implicit)
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", text)
    if m:
        d, mon, yr = m.groups()
        mon_num = _MONTHS.get(mon[:3].lower())
        if mon_num:
            iso = f"{yr}-{mon_num}-{d.zfill(2)}"
            return iso, iso

    return None, None


class HssAdapter(BaseAdapter):
    """Adapter for JPMA & Hoylake Sailing School (https://www.hss.ac.uk)."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []

        # --- Step 1: scrape the main course-dates page ---
        try:
            resp = session.get(COURSE_DATES_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("HSS course-dates fetch failed: %s", exc)
            return []
        time.sleep(2)

        try:
            offerings = self._parse_dates_page(resp.text, COURSE_DATES_URL, provider)
            all_offerings.extend(offerings)
        except Exception as exc:
            logger.warning("HSS course-dates parse failed: %s", exc)

        # --- Step 2: scrape individual course detail pages ---
        for course_id, detail_url in _COURSE_DETAIL_PAGES.items():
            # Skip if we already have live dates for this course
            if any(o.course_id == course_id for o in all_offerings):
                continue
            try:
                resp = session.get(detail_url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("HSS detail page fetch failed %s: %s", detail_url, exc)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_detail_page(
                    resp.text, detail_url, course_id, provider
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning(
                    "HSS detail page parse failed %s: %s", detail_url, exc
                )

        logger.info("HSS adapter: %d offerings total", len(all_offerings))
        return all_offerings

    # ------------------------------------------------------------------
    # Parsers
    # ------------------------------------------------------------------

    def _parse_dates_page(
        self, html: str, source_url: str, provider: dict
    ) -> list[Offering]:
        """
        Parse the /course-dates/ page.

        The page is structured as:
          <h2>Section Heading</h2>
          <p><strong>COURSE NAME</strong></p>
          <ul>
            <li>– 3rd – 7th August 2026</li>
            ...
          </ul>

        Scope rules:
        - A section heading (h2/h3/h4) always resets the current course context.
          If the heading text matches a known STCW course, that course becomes
          active; otherwise the context is cleared.
        - A <strong>/<b>/<p> course-name block within a section similarly sets
          or clears the active course.
        - Dates are only collected while a course context is active.
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        current_course_id: str | None = None

        # Walk every element in document order
        for tag in soup.find_all(["h2", "h3", "h4", "p", "li", "strong", "b"]):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue

            is_heading = tag.name in ("h2", "h3", "h4")

            # Any heading resets the section scope
            if is_heading:
                current_course_id = _course_id_from_text(text)
                continue

            # A bold/strong element or standalone <p> that looks like a course
            # title also resets scope for its subsection
            if tag.name in ("strong", "b") or (
                tag.name == "p" and len(text) < 120
            ):
                cid = _course_id_from_text(text)
                if cid:
                    # Matched a known STCW course — activate it
                    current_course_id = cid
                    continue
                # A new non-STCW course title closes the previous STCW scope
                # (only if it looks like a real course name, not a footnote)
                if (
                    current_course_id is not None
                    and len(text) < 120
                    and not re.search(
                        r"\btbc\b|contact|provisional|on.demand", text, re.I
                    )
                    and re.search(r"[A-Z]{2,}|course|training", text, re.I)
                ):
                    current_course_id = None
                continue

            if current_course_id is None:
                continue

            # <li> items are the actual date bullets
            clean = re.sub(r"^[-–—\s]+", "", text).strip()
            # Skip "TBC" / "on demand" / "contact" lines
            if re.search(r"\btbc\b|on.demand|contact|provisional", clean, re.I):
                continue

            start_iso, end_iso = _parse_date_range(clean)
            if not start_iso:
                continue

            key = f"{current_course_id}-{start_iso}"
            if key in seen:
                continue
            seen.add(key)

            offerings.append(
                Offering(
                    id=f"{current_course_id}-hss-{start_iso}",
                    course_id=current_course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso or start_iso,
                    timezone="Europe/London",
                    duration_days=_DURATION.get(current_course_id),
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(provider.get("website", BASE_URL)),
                    source_url=source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "HSS dates page: %d offerings from %s", len(offerings), source_url
        )
        return offerings

    def _parse_detail_page(
        self, html: str, source_url: str, course_id: str, provider: dict
    ) -> list[Offering]:
        """
        Parse a course detail page.  Dates may appear in paragraphs or list
        items; 'TBC' entries are skipped.
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        for tag in soup.find_all(["li", "p", "td"]):
            text = tag.get_text(" ", strip=True)
            if not text:
                continue
            if re.search(r"\btbc\b|on.demand|contact|provisional", text, re.I):
                continue

            clean = re.sub(r"^[-–—\s]+", "", text).strip()
            start_iso, end_iso = _parse_date_range(clean)
            if not start_iso:
                continue

            key = f"{course_id}-{start_iso}"
            if key in seen:
                continue
            seen.add(key)

            offerings.append(
                Offering(
                    id=f"{course_id}-hss-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso or start_iso,
                    timezone="Europe/London",
                    duration_days=_DURATION.get(course_id),
                    price=None,
                    currency=None,
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
            "HSS detail page: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            source_url,
        )
        return offerings
