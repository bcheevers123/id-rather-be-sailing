"""Professional Yacht Training (PYT) South Africa adapter.

PYT runs courses from Durban, Cape Town, Hout Bay, and Simons Town.
All locations share a single website (https://pyt.co.za/) and a single
WordPress-based calendar that exposes a JSON AJAX endpoint.

The calendar plugin is ``pyt-course-calendar-csv``. It responds to:
    GET https://pyt.co.za/wp-admin/admin-ajax.php
        ?action=get_calendar_events
        &nonce=<nonce>        # scraped fresh from the calendar page
        &year=<YYYY>
        &month=<M>            # 1-12

Each event has fields: id, title, start, end, url, description, color,
category, duration.  There is no per-event location field — the calendar
is a single shared view for all PYT locations.

Strategy:
- Scan forward ~12 months from today.
- Filter to STCW category events (category == "STCW") plus individual
  STCW sub-modules detected by title keyword matching.
- Because location is not in the API data, map provider_id from the
  provider dict passed in by the pipeline; all four PYT providers share
  the same website so we cannot split by location automatically.
- Dedup by event ID so multi-month scans don't double-count events that
  span month boundaries.
"""
import html as html_mod
import logging
import re
import time
from datetime import datetime, date, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://pyt.co.za"
CALENDAR_PAGE = f"{BASE_URL}/pyt-calendar/"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"
TIMEZONE = "Africa/Johannesburg"

# Months ahead to scan (covers current + 11 future months)
MONTHS_AHEAD = 12

# Maps title/description keywords to normalised STCW course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prev|fire.fight|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.*social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fight|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
    # Catch-all for full STCW Basic Safety Training (all four modules)
    (re.compile(r"stcw.basic.safety|basic.safety.training", re.I), "pst"),
    (re.compile(r"\bstcw\b", re.I), "pst"),
]


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _month_range(months_ahead: int) -> list[tuple[int, int]]:
    """Return list of (year, month) tuples starting from current month."""
    today = date.today()
    result = []
    y, m = today.year, today.month
    for _ in range(months_ahead):
        result.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


class PytZaAdapter(BaseAdapter):
    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: fetch the calendar page to get a fresh nonce
        try:
            resp = session.get(CALENDAR_PAGE, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("PYT ZA: calendar page fetch failed: %s", exc)
            return []
        time.sleep(2)

        nonce = self._extract_nonce(resp.text)
        if not nonce:
            logger.warning("PYT ZA: could not extract nonce from calendar page")
            return []

        # Step 2: fetch events for each month
        all_events: list[dict] = []
        seen_ids: set[int] = set()

        for year, month in _month_range(MONTHS_AHEAD):
            try:
                r = session.get(
                    AJAX_URL,
                    params={
                        "action": "get_calendar_events",
                        "nonce": nonce,
                        "year": year,
                        "month": month,
                    },
                    timeout=20,
                )
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                logger.warning(
                    "PYT ZA: AJAX fetch failed for %d-%02d: %s", year, month, exc
                )
                time.sleep(2)
                continue
            time.sleep(2)

            if not data.get("success"):
                logger.warning(
                    "PYT ZA: AJAX returned success=false for %d-%02d", year, month
                )
                continue

            for event in data.get("data", []):
                eid = event.get("id")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                all_events.append(event)

        if not all_events:
            logger.warning("PYT ZA: no events found")
            return []

        # Step 3: filter to STCW events and build Offerings
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for event in all_events:
            category = event.get("category", "")
            title_raw = html_mod.unescape(event.get("title", ""))
            description = html_mod.unescape(event.get("description", ""))
            combined = f"{category} {title_raw} {description}"

            course_id = _course_id_from_text(combined)
            if not course_id:
                continue  # Not an STCW course

            start_date = event.get("start", "")
            end_date = event.get("end", "") or start_date
            if not start_date:
                continue

            # Validate date format
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                logger.warning("PYT ZA: invalid date for event %s", event.get("id"))
                continue

            event_url = event.get("url", "")
            duration_str = event.get("duration")
            try:
                duration_days = float(duration_str) if duration_str else None
            except (ValueError, TypeError):
                duration_days = None

            offering_id = f"{course_id}-pyt-za-{event.get('id', start_date)}"

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=end_date,
                    timezone=TIMEZONE,
                    duration_days=duration_days,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(event_url),
                    source_url=CALENDAR_PAGE,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "PYT ZA: %d STCW offerings for provider %s",
            len(offerings),
            provider.get("id"),
        )
        return offerings

    def _extract_nonce(self, html: str) -> str | None:
        """Extract the calendar nonce from the page HTML."""
        m = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', html)
        if m:
            return m.group(1)
        # Fallback: look for pytCalendar nonce
        m2 = re.search(r'pytCalendar\s*=\s*\{[^}]*"nonce"\s*:\s*"([^"]+)"', html)
        if m2:
            return m2.group(1)
        return None
