"""UHI North, West and Hebrides adapter.

UHI NWH lists STCW short courses on Eventbrite:
    https://www.eventbrite.co.uk/o/uhi-north-west-and-hebrides-31780081169

Strategy:
1.  Fetch the Eventbrite organiser page and extract the embedded ``__NEXT_DATA__``
    JSON to enumerate upcoming event series IDs.
2.  For each event whose title matches an STCW keyword, call the public
    Eventbrite v3 API ``/api/v3/series/{id}/events/`` to get individual dated
    occurrences.
3.  Emit one Offering per ``status == "live"`` occurrence.

No auth token is required – both endpoints are publicly accessible.

Courses detected: pst, efa  (the two confirmed STCW series on this organiser).
Other STCW IDs (fpff, pssr, pscrb, aff, mfa, mc, frb) are included in the
keyword map and will be picked up automatically if added by the provider.
"""

import json
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

ORGANISER_URL = (
    "https://www.eventbrite.co.uk/o/uhi-north-west-and-hebrides-31780081169"
)
SERIES_EVENTS_API = (
    "https://www.eventbrite.co.uk/api/v3/series/{series_id}/events/"
    "?order_by=start_asc&page_size=50&expand=venue"
)

# Maps keyword patterns in event title -> canonical course_id.
# Evaluated in order; first match wins.
_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.tech|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"fire.prevention|fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fight|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]\bmc\b[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# Require "stcw" or "mca" in the title so we don't grab non-maritime first-aid
_STCW_GATE = re.compile(r"\b(stcw|mca)\b", re.I)


def _identify_course(title: str) -> str | None:
    """Return canonical course_id if ``title`` matches an STCW keyword, else None."""
    padded = f" {title} "
    for pattern, course_id in _COURSE_MAP:
        if pattern.search(padded):
            return course_id
    return None


class UhiNwhAdapter(BaseAdapter):
    """Adapter for UHI North, West and Hebrides STCW courses via Eventbrite."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # ------------------------------------------------------------------ #
        # Step 1 – fetch the organiser page and extract the embedded JSON     #
        # ------------------------------------------------------------------ #
        try:
            resp = session.get(ORGANISER_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("UHI NWH organiser page fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            series_entries = _extract_series_entries(resp.text)
        except Exception as exc:
            logger.warning("UHI NWH organiser page parse failed: %s", exc)
            return []

        if not series_entries:
            logger.warning("UHI NWH: no STCW series entries found on organiser page")
            return []

        logger.info("UHI NWH: found %d STCW series to expand", len(series_entries))

        # ------------------------------------------------------------------ #
        # Step 2 – expand each series into individual dated occurrences       #
        # ------------------------------------------------------------------ #
        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for entry in series_entries:
            series_id = entry["series_id"]
            course_id = entry["course_id"]
            parent_url = entry["parent_url"]

            try:
                resp = session.get(
                    SERIES_EVENTS_API.format(series_id=series_id),
                    timeout=20,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning(
                    "UHI NWH series fetch failed (%s / %s): %s",
                    course_id, series_id, exc,
                )
                time.sleep(2)
                continue

            time.sleep(2)

            try:
                offerings = _parse_series_events(
                    data, course_id, series_id, parent_url, provider, now
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning(
                    "UHI NWH series parse failed (%s / %s): %s",
                    course_id, series_id, exc,
                )

        logger.info("UHI NWH adapter: %d offerings total", len(all_offerings))
        return all_offerings


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _extract_series_entries(html: str) -> list[dict]:
    """Parse ``__NEXT_DATA__`` from the Eventbrite organiser page HTML.

    Returns a list of ``{series_id, course_id, parent_url}`` dicts for every
    upcoming event that matches an STCW keyword.
    """
    # Locate the JSON blob embedded in the page
    m = re.search(r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ script tag not found")

    data = json.loads(m.group(1))
    upcoming = data.get("props", {}).get("pageProps", {}).get("upcomingEvents", [])

    entries: list[dict] = []
    seen: set[str] = set()

    for event in upcoming:
        name: str = event.get("name", "")
        event_id: str = str(event.get("id", ""))
        url: str = event.get("url", "")

        # Only process events with "stcw" or "mca" in the title
        if not _STCW_GATE.search(name):
            continue

        course_id = _identify_course(name)
        if course_id is None:
            logger.debug("UHI NWH: skipping unrecognised STCW event: %s", name)
            continue

        # The parent/series ID is the same as the event ID for series parents
        if event_id and event_id not in seen:
            seen.add(event_id)
            entries.append({
                "series_id": event_id,
                "course_id": course_id,
                "parent_url": url,
            })

    return entries


def _parse_series_events(
    data: dict,
    course_id: str,
    series_id: str,
    parent_url: str,
    provider: dict,
    now: str,
) -> list[Offering]:
    """Convert a ``/api/v3/series/{id}/events/`` response into Offerings."""
    events = data.get("events", [])
    offerings: list[Offering] = []
    seen: set[str] = set()

    for event in events:
        status = event.get("status", "")
        if status not in ("live", "started"):
            continue

        start_info = event.get("start") or {}
        end_info = event.get("end") or {}

        start_local: str = start_info.get("local", "")
        end_local: str = end_info.get("local", "")
        tz: str = start_info.get("timezone", "Europe/London")

        if not start_local:
            continue

        try:
            start_date = start_local[:10]   # "YYYY-MM-DD"
            end_date = end_local[:10] if end_local else start_date
        except Exception:
            continue

        child_url: str = event.get("url", parent_url)
        child_id: str = str(event.get("id", ""))

        # Derive duration in days
        try:
            d0 = datetime.fromisoformat(start_local)
            d1 = datetime.fromisoformat(end_local)
            duration_days: float | None = max(1.0, round((d1 - d0).total_seconds() / 86400, 1))
        except Exception:
            duration_days = None

        # Price from ticket_classes if available
        price: float | None = None
        currency: str | None = "GBP"
        for tc in event.get("ticket_classes", []):
            cost = tc.get("cost") or {}
            val = cost.get("value")
            if val is not None:
                try:
                    price = float(val) / 100  # Eventbrite stores in pence
                except Exception:
                    pass
                currency = cost.get("currency", "GBP")
                break

        # Venue / location
        venue = event.get("venue") or {}
        venue_name: str = venue.get("name", "")
        city: str = (venue.get("address") or {}).get("city", "")
        location_str = ", ".join(filter(None, [venue_name, city])) or None

        offering_id = f"{course_id}-uhi-nwh-{start_date}"
        if child_id:
            offering_id = f"{course_id}-uhi-nwh-{start_date}-{child_id}"

        if offering_id in seen:
            continue
        seen.add(offering_id)

        offerings.append(
            Offering(
                id=offering_id,
                course_id=course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=end_date,
                timezone=tz,
                duration_days=duration_days,
                price=price,
                currency=currency,
                vat_included=None,
                delivery_format="in_person",
                availability=location_str,
                booking_url=safe_url(child_url or parent_url),
                source_url=parent_url,
                last_verified=now,
                freshness_status="verified",
            )
        )

    return offerings
