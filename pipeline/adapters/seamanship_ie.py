"""The Seamanship Centre (seamanship.ie) adapter.

Uses The Events Calendar (Tribe Events) REST API to fetch all upcoming
events, then filters and maps to known STCW course IDs.

API endpoint: GET /wp-json/tribe/events/v1/events
  ?per_page=50&start_date=YYYY-MM-DD

Response top-level fields used:
  events[]  – list of event objects
  next_rest_url – URL for the next page (absent on last page)

Per-event fields used:
  title, start_date, end_date, cost, url, timezone, id
"""
import logging
import re
import time
from datetime import date, datetime, timezone

import requests

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

# seamanship.ie blocks bot-identified User-Agent strings (returns 403).
# A realistic browser UA is required for the Tribe Events REST API to respond.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

BASE_URL = "https://seamanship.ie"
API_URL = f"{BASE_URL}/wp-json/tribe/events/v1/events"
TIMEZONE = "Europe/Dublin"

# Maps title keywords to normalised course IDs.
# Checked in order — first match wins.
# AFF listed before FPFF so "Advanced Fire Fighting" doesn't match the FPFF pattern.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"advanced\s+fire\s+fight|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"fire\s+prevent|fire.{0,5}fight|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary\s+first\s+aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal\s+survival\s+tech|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"personal\s+safety.{0,30}social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency\s+in\s+survival\s+craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"medical\s+first\s+aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical\s+care\s+aboard|[^a-z]\bmc\b[^a-z]", re.I), "mc"),
    (re.compile(r"fast\s+rescue\s+boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# Matches euro prices like "€250", "€850.00", "€1,500"
_COST_RE = re.compile(r"€\s*([\d,]+(?:\.\d+)?)")


def _course_id_from_title(title: str) -> str | None:
    """Return a normalised course ID by matching the event title against the keyword map."""
    padded = f" {title} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_cost(cost_str: str | None) -> tuple[float | None, str | None]:
    """Parse a cost string like '€250' or '€850.00' → (250.0, 'EUR')."""
    if not cost_str:
        return None, None
    m = _COST_RE.search(cost_str)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
        return price, "EUR"
    except ValueError:
        return None, None


def _duration_days(start: str, end: str) -> float | None:
    """Compute inclusive duration in days from ISO date strings (YYYY-MM-DD prefix)."""
    try:
        s = date.fromisoformat(start[:10])
        e = date.fromisoformat(end[:10])
        return float((e - s).days + 1)
    except (ValueError, TypeError):
        return None


class SeamanshipIeAdapter(BaseAdapter):
    """Adapter for The Seamanship Centre, Killybegs, Ireland."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()

        next_url: str | None = f"{API_URL}?per_page=50&start_date={today}"
        page = 0

        while next_url:
            page += 1
            try:
                resp = session.get(next_url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "seamanship.ie API fetch failed (page %d): %s", page, exc
                )
                return all_offerings
            time.sleep(2)

            try:
                data = resp.json()
            except Exception as exc:
                logger.warning(
                    "seamanship.ie JSON parse failed (page %d): %s", page, exc
                )
                return all_offerings

            events = data.get("events", [])
            if not events:
                break

            for event in events:
                title: str = event.get("title", "")
                course_id = _course_id_from_title(title)
                if not course_id:
                    continue

                start_date = (event.get("start_date") or "")[:10]
                end_date = (event.get("end_date") or "")[:10]
                if not start_date:
                    continue
                if not end_date:
                    end_date = start_date

                offering_id = f"{course_id}-seamanship-ie-{start_date}"
                if offering_id in seen_ids:
                    # Append the Tribe event ID to keep duplicates distinct
                    offering_id = f"{offering_id}-{event.get('id', '')}"
                seen_ids.add(offering_id)

                event_url: str = event.get("url", "") or ""
                price, currency = _parse_cost(event.get("cost"))

                all_offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=end_date,
                        timezone=TIMEZONE,
                        duration_days=_duration_days(start_date, end_date),
                        price=price,
                        currency=currency,
                        vat_included=True,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(event_url),
                        source_url=event_url or API_URL,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

            next_url = data.get("next_rest_url") or None

        logger.info(
            "seamanship.ie adapter: %d STCW offerings across %d API pages",
            len(all_offerings),
            page,
        )
        return all_offerings
