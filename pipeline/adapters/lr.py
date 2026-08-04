"""Lloyd's Register EMEA maritime training adapter.

Investigation findings
----------------------
robots.txt (https://www.lr.org/robots.txt) only disallows /episerver/ and
/utils/.  Our user-agent is not restricted.

The main training listing page at lr.org/en/services/maritime-training/ is
accessible and lists ~40 courses across four categories.  Individual course
pages each carry a small inline schedule (start date, location, availability)
rendered server-side, plus a "Book now" / "Explore course dates" link pointing
to the external training portal (training-portal.lr.org).  The training portal
itself returns HTTP 403 for programmatic requests.

Course-ID mapping
-----------------
Only ISPS-related courses map to project course IDs:
  sso  — ISPS Ship Security Officer (3-day, MCA-approved)

All other LR courses (ISM auditing, technical efficiency, leadership, rules &
regulations) do not match the project's STCW-focused course_id taxonomy.

Scraping strategy
-----------------
For each mapped course page we:
  1. GET the page with requests (2 s inter-request delay).
  2. Parse inline schedule rows from the rendered HTML.
  3. Extract start date, location, availability, and a booking URL.

Schedule rows on LR course pages follow this pattern (observed on multiple
pages):
  <div class="course-dates__item"> or similar container with:
    - A date element (e.g. <time datetime="2026-12-15"> or plain text)
    - A location string
    - An availability badge ("Places Available", "Fully Booked", etc.)
    - A "Book now" <a href="https://training-portal.lr.org/...">

Because the exact class names vary slightly across course pages, we use a
multi-strategy parser (datetime attributes → structured divs → full-text scan).
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
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE = "https://www.lr.org"
ADAPTER_SLUG = "lr"

# Map project course_id → relative LR course page path.
# Only include courses that genuinely appear in the LR catalogue.
COURSE_PAGES: dict[str, str] = {
    "sso": (
        "/en/services/maritime-training/maritime-management-systems/"
        "isps-ship-security-officer/"
    ),
}

# Regex: match ISO dates (2026-12-15), UK long (15 December 2026 / 15 Dec 2026),
# US-ish (December 15, 2026), and DD/MM/YYYY.
_MONTH = (
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
)
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2})"  # ISO
    r"|\b(\d{1,2})\s+(" + _MONTH + r")\s+(\d{4})\b"  # DD Mon YYYY
    r"|\b(" + _MONTH + r")\s+(\d{1,2}),?\s+(\d{4})\b"  # Mon DD, YYYY
    r"|\b(\d{2})/(\d{2})/(\d{4})\b",  # DD/MM/YYYY
    re.I,
)

_PORTAL_HREF_RE = re.compile(r"training-portal\.lr\.org", re.I)

# Availability patterns that signal a course run is NOT bookable.
_CANCELLED_RE = re.compile(r"\b(cancel|full(?:ly)?\s+book|sold\s+out)\b", re.I)


def _parse_date(text: str) -> str | None:
    """Return ISO date string from a human-readable date fragment, or None."""
    text = text.strip()
    try:
        return dateutil_parser.parse(text, fuzzy=True).date().isoformat()
    except Exception:
        return None


def _extract_inline_dates(soup: BeautifulSoup, source_url: str) -> list[dict]:
    """
    Return a list of date-record dicts from a parsed LR course page.

    Each dict has keys: start_date (ISO str), availability (str|None),
    booking_url (str|None).

    Strategy 1 — Elements with a machine-readable ``datetime`` attribute.
    Strategy 2 — Divs/spans with class names suggesting schedule rows.
    Strategy 3 — Full-text scan for date strings near "book" or "places" text.
    """
    records: list[dict] = []
    seen_dates: set[str] = set()

    # ---- Strategy 1: <time datetime="…"> elements -------------------------
    for time_el in soup.find_all("time", attrs={"datetime": True}):
        raw = time_el["datetime"]
        start_date = _parse_date(raw)
        if not start_date or start_date in seen_dates:
            continue
        seen_dates.add(start_date)
        # Look for availability and booking link in the surrounding container
        container = time_el.find_parent(
            ["div", "li", "tr", "article"],
            class_=re.compile(r"course|date|sched|session|event|row|item", re.I),
        ) or time_el.parent
        availability, booking_url = _container_meta(container)
        records.append({
            "start_date": start_date,
            "availability": availability,
            "booking_url": booking_url,
        })

    if records:
        return records

    # ---- Strategy 2: schedule-ish div/li containers -----------------------
    containers = soup.find_all(
        ["div", "li", "tr"],
        class_=re.compile(r"course.date|sched|session|event.row|date.row|date.item", re.I),
    )
    for container in containers:
        text = container.get_text(" ", strip=True)
        start_date = _parse_date(text)
        if not start_date or start_date in seen_dates:
            continue
        seen_dates.add(start_date)
        availability, booking_url = _container_meta(container)
        records.append({
            "start_date": start_date,
            "availability": availability,
            "booking_url": booking_url,
        })

    if records:
        return records

    # ---- Strategy 3: full-page text scan -----------------------------------
    full_text = soup.get_text(" ", strip=True)
    # Find all date matches in the page text; check nearby context for "book"
    for m in _DATE_RE.finditer(full_text):
        raw_match = m.group(0)
        start_date = _parse_date(raw_match)
        if not start_date or start_date in seen_dates:
            continue
        # Context window around match
        ctx_start = max(0, m.start() - 200)
        ctx_end = min(len(full_text), m.end() + 200)
        ctx = full_text[ctx_start:ctx_end]
        # Only include if context suggests this is a scheduled session
        if not re.search(r"\b(book|place|session|available|enrol|registr)\b", ctx, re.I):
            continue
        seen_dates.add(start_date)
        # Try to find a portal link in the whole page
        portal_link = _find_portal_link(soup)
        availability = None
        if re.search(r"\bplaces?\s+available\b", ctx, re.I):
            availability = "Places available"
        elif re.search(r"\bfully\s+book|sold\s+out\b", ctx, re.I):
            availability = "Fully booked"
        records.append({
            "start_date": start_date,
            "availability": availability,
            "booking_url": portal_link,
        })

    return records


def _container_meta(container) -> tuple[str | None, str | None]:
    """Return (availability_text, booking_url) from a schedule container."""
    if container is None:
        return None, None

    text = container.get_text(" ", strip=True)
    availability: str | None = None
    if re.search(r"\bplaces?\s+available\b", text, re.I):
        availability = "Places available"
    elif re.search(r"\bfully\s+book|sold\s+out\b", text, re.I):
        availability = "Fully booked"

    # Prefer a direct portal booking link
    booking_url: str | None = None
    for a in container.find_all("a", href=True):
        href = a["href"]
        if _PORTAL_HREF_RE.search(href):
            booking_url = safe_url(href)
            break
    if not booking_url:
        for a in container.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http"):
                booking_url = safe_url(href)
                break
            elif href.startswith("/"):
                booking_url = safe_url(BASE + href)
                break

    return availability, booking_url


def _find_portal_link(soup: BeautifulSoup) -> str | None:
    """Return the first training-portal.lr.org link found anywhere on the page."""
    for a in soup.find_all("a", href=_PORTAL_HREF_RE):
        url = safe_url(a["href"])
        if url:
            return url
    return None


class LrAdapter(BaseAdapter):
    """Scrapes inline course dates from Lloyd's Register EMEA course pages.

    Fetches each mapped course page with a 2-second inter-request delay.
    Parses server-rendered schedule rows.  Falls back to an empty list if the
    page is unreachable or contains no parseable dates.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []

        for course_id, path in COURSE_PAGES.items():
            url = BASE + path
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("LrAdapter: GET %s failed: %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                page_offerings = self._parse_page(
                    resp.text, provider, course_id, url, now
                )
                offerings.extend(page_offerings)
                logger.info(
                    "LrAdapter: %d offering(s) from %s", len(page_offerings), url
                )
            except Exception as exc:
                logger.warning("LrAdapter: parse failed for %s: %s", url, exc)

        return offerings

    def _parse_page(
        self,
        html: str,
        provider: dict,
        course_id: str,
        source_url: str,
        now: str,
    ) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        date_records = _extract_inline_dates(soup, source_url)

        if not date_records:
            logger.debug("LrAdapter: no inline dates found at %s", source_url)
            return []

        offerings: list[Offering] = []
        seen: set[str] = set()

        for rec in date_records:
            # Skip cancelled / fully-booked runs
            if rec.get("availability") and _CANCELLED_RE.search(rec["availability"]):
                continue

            start_date = rec["start_date"]
            key = f"{course_id}-{start_date}"
            if key in seen:
                continue
            seen.add(key)

            offering_id = (
                f"{provider['id']}-{ADAPTER_SLUG}-{course_id}-{start_date}"
            )

            booking_url = rec.get("booking_url") or safe_url(BASE + COURSE_PAGES[course_id])

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=start_date,  # LR pages don't always show end date
                    timezone="Europe/London",
                    duration_days=None,
                    price=None,  # LR does not display prices on public pages
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=rec.get("availability"),
                    booking_url=booking_url,
                    source_url=source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
