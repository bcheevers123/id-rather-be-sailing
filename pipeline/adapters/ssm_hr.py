"""Split Ship Management (SSM, Split, Croatia) adapter.

SSM uses the My Calendar WordPress plugin.  Course schedule data is exposed
via the REST endpoint:

    GET https://ssm.hr/wp-json/my-calendar/v1/events?from=YYYY-MM-DD&to=YYYY-MM-DD

Each event object carries:
    event_title  – course name (English and Croatian variants)
    occur_begin  – "YYYY-MM-DD HH:MM:SS"  start date of this run
    occur_end    – "YYYY-MM-DD HH:MM:SS"  end date of this run
    event_id     – integer identifier

The API does NOT expose pricing; prices must be obtained from individual
course pages, but those pages use an HTML contact form with no structured
price data, so price/currency are omitted (None).

robots.txt: single Disallow for a plugin JSON file; course/schedule pages
are fully permitted.

STCW course mapping (SSM course code → our course_id):
    D2  → pst, fpff, efa, pssr  (Basic Safety Training is the full BST bundle)
    D12 → aff
    D17 → pscrb
    D18 → frb
    D19 → mfa
    D20 → mc

Note: SSM packages PST/FPFF/EFA/PSSR as a single "Basic Safety Training"
block (D2).  We emit one offering per course_id covered by D2 for the same
date so the data appears in each relevant course bucket.

Delay: 2 s between requests to the same domain (one API call per year-range).
"""

import logging
import time
from datetime import date, datetime, timezone

import requests

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

_API_URL = "https://ssm.hr/wp-json/my-calendar/v1/events"

# How many calendar years ahead to fetch (inclusive of current year).
_FETCH_YEARS = 2

# Maps lowercase tokens found in event_title to our course_id(s).
# A title may map to multiple course_ids (e.g. BST covers pst/fpff/efa/pssr).
_TITLE_MAP: list[tuple[str, list[str]]] = [
    ("d2",          ["pst", "fpff", "efa", "pssr"]),
    ("basic safety", ["pst", "fpff", "efa", "pssr"]),
    ("temeljna sigurnost", ["pst", "fpff", "efa", "pssr"]),
    ("d12",         ["aff"]),
    ("fire fighting", ["aff"]),
    ("gašenje požara", ["aff"]),
    ("d17",         ["pscrb"]),
    ("survival craft", ["pscrb"]),
    ("splav za spašavanje", ["pscrb"]),
    ("d18",         ["frb"]),
    ("fast rescue boat", ["frb"]),
    ("brzi spasilački čamac", ["frb"]),
    ("d19",         ["mfa"]),
    ("first aid aboard", ["mfa"]),
    ("prva pomoć", ["mfa"]),
    ("d20",         ["mc"]),
    ("medical care aboard", ["mc"]),
    ("medicinska skrb", ["mc"]),
]

_COURSE_PAGE_URLS: dict[str, str] = {
    "pst":   "https://ssm.hr/en/course/d2-basic-safety-training/",
    "fpff":  "https://ssm.hr/en/course/d2-basic-safety-training/",
    "efa":   "https://ssm.hr/en/course/d2-basic-safety-training/",
    "pssr":  "https://ssm.hr/en/course/d2-basic-safety-training/",
    "aff":   "https://ssm.hr/en/course/d12-advanced-fire-fighting/",
    "pscrb": "https://ssm.hr/en/course/d17-proficiency-in-survival-craft-and-rescue-boat/",
    "frb":   "https://ssm.hr/en/course/d18-certificate-in-proficiency-in-fast-rescue-boats/",
    "mfa":   "https://ssm.hr/en/course/d19-proficiency-in-first-aid-aboard-ship/",
    "mc":    "https://ssm.hr/en/course/d20-proficiency-in-medical-care-aboard-ship/",
}


def _resolve_course_ids(title: str) -> list[str]:
    """Map an event title to one or more course_ids, or [] if unrecognised.

    Course-code tokens (e.g. "d2", "d20") are matched as whole words so that
    "d20" does not accidentally match the "d2" entry.  Phrase tokens
    (e.g. "basic safety") are matched as plain substrings.
    """
    import re as _re
    lower = title.lower()
    for token, ids in _TITLE_MAP:
        # Course-code tokens are short alphanumerics (e.g. "d2", "d12", "d20").
        # Use a word-boundary match so "d2" does not match inside "d20".
        if _re.match(r"^[a-z]\d+$", token):
            if _re.search(r"\b" + _re.escape(token) + r"\b", lower):
                return ids
        else:
            if token in lower:
                return ids
    return []


def _parse_date(dt_str: str) -> str | None:
    """Convert 'YYYY-MM-DD HH:MM:SS' to 'YYYY-MM-DD', returning None on error."""
    if not dt_str:
        return None
    try:
        return datetime.strptime(dt_str[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


class SsmHrAdapter(BaseAdapter):
    """Fetches STCW course dates from SSM Split via the My Calendar REST API."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        today = date.today()
        year_from = today.year
        year_to = today.year + _FETCH_YEARS - 1

        # Fetch the full window in one request to minimise round-trips.
        params = {
            "from": f"{year_from}-01-01",
            "to": f"{year_to}-12-31",
        }

        try:
            resp = session.get(_API_URL, params=params, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("SsmHr: API fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            raw = resp.json()
        except Exception as exc:
            logger.warning("SsmHr: JSON decode failed: %s", exc)
            return []

        # The My Calendar REST API returns either:
        #   - an empty list  []  when no events exist in the window, OR
        #   - a dict keyed by date string "YYYY-MM-DD", each value being a
        #     list of event objects for that date.
        if isinstance(raw, list):
            if not raw:
                logger.info(
                    "SsmHr: API returned 0 events for %s–%s "
                    "(schedule not yet published)",
                    params["from"],
                    params["to"],
                )
                return []
            # Flat list fallback (not currently observed but handled for safety)
            all_events: list[dict] = raw
        elif isinstance(raw, dict):
            all_events = [
                event
                for day_events in raw.values()
                if isinstance(day_events, list)
                for event in day_events
            ]
        else:
            logger.warning("SsmHr: unexpected API response type: %s", type(raw))
            return []

        if not all_events:
            logger.info("SsmHr: no events in API response")
            return []

        offerings: list[Offering] = []
        # Deduplicate by (course_id, start_date) — the API returns both
        # English and Croatian editions of the same session on the same date.
        seen: set[tuple[str, str]] = set()

        for event in all_events:
            title = event.get("event_title") or ""
            course_ids = _resolve_course_ids(title)
            if not course_ids:
                continue

            # event_begin / event_end are plain "YYYY-MM-DD" date strings
            # representing the actual course start/end days.
            # occur_begin / occur_end include a dummy time (08:30-09:30) and
            # are NOT reliable for computing course duration.
            start_date = _parse_date(event.get("event_begin") or "")
            end_date = _parse_date(event.get("event_end") or "")
            if not start_date:
                continue
            if not end_date or end_date < start_date:
                end_date = start_date

            for course_id in course_ids:
                key = (course_id, start_date)
                if key in seen:
                    continue
                seen.add(key)

                course_page = safe_url(_COURSE_PAGE_URLS.get(course_id))

                offerings.append(
                    Offering(
                        id=f"{course_id}-split-ship-management-{start_date}",
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=end_date,
                        timezone="Europe/Zagreb",
                        duration_days=None,
                        price=None,
                        currency=None,
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=course_page,
                        source_url=_API_URL,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        logger.info(
            "SsmHr adapter: %d offerings for provider %s",
            len(offerings),
            provider["id"],
        )
        return offerings
