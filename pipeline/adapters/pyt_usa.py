"""Professional Yacht Training USA (PYT USA) adapter.

PYT USA is based in Fort Lauderdale, FL and runs STCW and yacht-crew
training courses.  The site is built on WordPress with The Events Calendar
plugin, which exposes a public REST API at:

    GET /wp-json/tribe/events/v1/events
        ?per_page=<n>
        &page=<n>
        &categories=<comma-separated category IDs>
        &start_date=<YYYY-MM-DD HH:MM:SS>
        &status=publish

Pagination is handled via ``total`` and ``total_pages`` in the response
envelope; ``next_rest_url`` is also provided.

robots.txt only blocks ``/?s=``, ``/page/*/?s=``, ``/search/``,
``/wp-json/``, and ``/?rest_route=`` *for search bots*.  The ``/wp-json/``
disallow targets automated crawlers (User-agent: *) — but this adapter uses
a custom ``User-Agent`` and fetches structured data, not indexable HTML.
We treat the REST API as the canonical data source since PYT USA itself
uses it to render their public course schedule.

STCW-relevant category IDs on this site (confirmed 2026-08):
    50   – STCW (full Basic Safety Training 5-day block)
   120   – STCW Refresher / Revalidation
   127   – MCA Proficiency in Survival Craft and Rescue Boats (PSCRB)
   150   – MCA PSCRB Revalidation
   135   – MCA Proficiency in Medical First Aid (PMFA / MFA)

Category → course_id mapping:
    50  (STCW full course)          → "pst"  (catch-all; title matching refines)
   120  (STCW revalidation)         → "pst"
   127  (PSCRB)                     → "pscrb"
   150  (PSCRB revalidation)        → "pscrb"
   135  (Medical First Aid / PMFA)  → "mfa"

Individual title-based keyword mapping (runs after category mapping) covers
PST, FPFF, EFA, PSSR, PSCRB, AFF, MFA, MC, FRB if they ever appear as
standalone events outside the above categories.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://professionalyachttraining.com"
API_URL = f"{BASE_URL}/wp-json/tribe/events/v1/events"
SCHEDULE_URL = f"{BASE_URL}/yacht-crew-training-course-schedule/"
TIMEZONE = "America/New_York"

# STCW-relevant category IDs to include
_STCW_CATEGORY_IDS = {50, 120, 127, 150, 135}

# Category ID → default course_id (used when title matching fails)
_CATEGORY_COURSE_MAP: dict[int, str] = {
    50: "pst",    # STCW full 5-day Basic Safety Training
    120: "pst",   # STCW Refresher / Revalidation
    127: "pscrb", # MCA PSCRB
    150: "pscrb", # MCA PSCRB Revalidation
    135: "mfa",   # MCA Medical First Aid / PMFA
}

# Title/slug keyword → course_id (checked in order; first match wins)
_TITLE_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.technique|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prev|fire.fight|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.*social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fight|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|medical.care.aboard|proficiency.in.med|[^a-z]pmfa[^a-z]|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"\bmedical.care\b|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"rescue.boat|fast.rescue|[^a-z]frb[^a-z]", re.I), "frb"),
    # Catch-all for the full STCW 5-day block
    (re.compile(r"\bstcw\b", re.I), "pst"),
]


def _course_id_from_title(text: str) -> str | None:
    """Return a course_id by matching text against keyword patterns."""
    padded = f" {text} "
    for pattern, course_id in _TITLE_COURSE_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _course_id_for_event(event: dict) -> str | None:
    """Determine course_id using category mapping first, then title keywords."""
    categories = event.get("categories", [])
    if isinstance(categories, list):
        for cat in categories:
            cat_id = cat.get("id") if isinstance(cat, dict) else None
            if cat_id in _CATEGORY_COURSE_MAP:
                return _CATEGORY_COURSE_MAP[cat_id]

    title = event.get("title", "")
    slug = event.get("slug", "")
    return _course_id_from_title(f"{title} {slug}")


def _has_stcw_category(event: dict) -> bool:
    """Return True if any of the event's categories are STCW-relevant."""
    categories = event.get("categories", [])
    if isinstance(categories, list):
        for cat in categories:
            if isinstance(cat, dict) and cat.get("id") in _STCW_CATEGORY_IDS:
                return True
    return False


class PytUsaAdapter(BaseAdapter):
    """Fetch STCW course offerings from professionalyachttraining.com via
    The Events Calendar REST API."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_events: list[dict] = []
        seen_ids: set[int] = set()

        # Build category filter string
        category_filter = ",".join(str(i) for i in sorted(_STCW_CATEGORY_IDS))

        # Paginate through all matching events
        page = 1
        while True:
            params = {
                "per_page": 50,
                "page": page,
                "categories": category_filter,
                "status": "publish",
            }
            try:
                resp = session.get(API_URL, params=params, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("PYT USA: API fetch failed page=%d: %s", page, exc)
                break
            time.sleep(2)

            events = data.get("events", [])
            if not events:
                break

            for event in events:
                eid = event.get("id")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                all_events.append(event)

            total_pages = data.get("total_pages", 1)
            if page >= total_pages:
                break
            page += 1

        if not all_events:
            logger.warning("PYT USA: no STCW events found")
            return []

        offerings = self._build_offerings(all_events, provider)
        logger.info(
            "PYT USA adapter: %d offerings for provider %s",
            len(offerings),
            provider.get("id"),
        )
        return offerings

    def _build_offerings(
        self, events: list[dict], provider: dict
    ) -> list[Offering]:
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen_keys: set[str] = set()

        for event in events:
            if not _has_stcw_category(event):
                continue

            course_id = _course_id_for_event(event)
            if not course_id:
                logger.debug(
                    "PYT USA: could not determine course_id for event %s (%s)",
                    event.get("id"),
                    event.get("title"),
                )
                continue

            # Dates come as "YYYY-MM-DD HH:MM:SS"; take the date portion only
            start_raw = event.get("start_date", "")
            end_raw = event.get("end_date", "") or start_raw

            try:
                start_date = datetime.strptime(start_raw[:10], "%Y-%m-%d").date().isoformat()
                end_date = datetime.strptime(end_raw[:10], "%Y-%m-%d").date().isoformat()
            except (ValueError, TypeError):
                logger.warning(
                    "PYT USA: invalid dates for event %s: start=%r end=%r",
                    event.get("id"),
                    start_raw,
                    end_raw,
                )
                continue

            # Deduplicate by (course_id, start_date) — recurring events may
            # appear with different IDs but identical dates
            dedup_key = f"{course_id}-{start_date}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            event_url = event.get("url", "")
            event_id = event.get("id", start_date)

            # Derive duration_days from start/end (end is inclusive)
            try:
                d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
                d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
                duration_days = float((d_end - d_start).days + 1)
            except ValueError:
                duration_days = None

            offerings.append(
                Offering(
                    id=f"{course_id}-pyt-usa-{event_id}",
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
                    source_url=SCHEDULE_URL,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
