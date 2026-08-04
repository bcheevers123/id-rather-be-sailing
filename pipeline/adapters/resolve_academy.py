"""Resolve Maritime Academy adapter.

Scrapes https://resolveacademy.com for STCW course schedules.

Technique: static HTML parsing of ``data-course`` JSON attributes embedded
in ``<input type="hidden">`` elements on each course product page.

Page structure:
  Each scheduled offering appears as::

      <input class="course-<timestamp>-<seat>-<product_id>"
             type="hidden"
             data-course="{...JSON...}">

  The JSON payload (HTML-entity-encoded) contains fields including:

  * ``start``     – ISO date string, e.g. ``"2026-08-05"``
  * ``end``       – ISO date string for the last calendar day shown
  * ``booking_end`` – ISO date string of the final *teaching* day (end - 1)
  * ``price``     – USD price as a string, e.g. ``"699"``
  * ``seat_count`` – available seats remaining
  * ``total_seats`` – total seats in session
  * ``url_course`` – canonical URL of the course product page
  * ``add_to_cart`` – WooCommerce product/variation ID
  * ``course_type`` – free-text course category label
  * ``past``      – boolean; ``true`` for already-passed sessions

  The adapter visits each known STCW course URL, parses these input elements,
  and maps ``course_type`` / URL slug to the project's normalised course IDs.

  Pages with 0 embedded dates (e.g. the $1 399 full BST, first-aid-cpr, and
  fast-rescue-boat) rely on the WooCommerce Bookings calendar widget, which
  loads dates dynamically via AJAX and does not expose them in static HTML.
  Those pages are silently skipped; the adapter returns only dates it can
  actually verify without a browser.

robots.txt: disallows only WooCommerce transient / upload directories and
``/wp-admin/``.  The course product pages used here are unrestricted.

Provider IDs: ``resolve-maritime-academy``, ``resolve-maritime-academy-2``.
Currency: USD (Fort Lauderdale, FL, USA).
Timezone: America/New_York.
"""
from __future__ import annotations

import html as _html_mod
import json
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

BASE_URL = "https://resolveacademy.com"

# Course product pages that carry embedded date JSON.
# Pages that use only the dynamic WC Bookings calendar are omitted.
_COURSE_PAGES: list[tuple[str, str]] = [
    # (url_slug, course_id)
    ("basic-safety-training-revalidation", "pst"),
    ("personal-survival-techniques-revalidation", "pst"),
    ("basic-firefighting", "fpff"),
    ("basic-firefighting-revalidation", "fpff"),
    ("advanced-firefighting-uscg", "aff"),
    ("mca-advanced-firefighting", "aff"),
    ("uscg-advanced-firefighting-revalidation", "aff"),
    ("mca-advanced-firefighting-updating", "aff"),
]

# Fallback: map course_type strings -> course_id
_COURSE_TYPE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"basic.training.revalid|pst.revalid", re.I), "pst"),
    (re.compile(r"personal.survival.technique", re.I), "pst"),
    (re.compile(r"fire.fight|firefight|fpff", re.I), "fpff"),
    (re.compile(r"advanced.fire|aff", re.I), "aff"),
    (re.compile(r"personal.safety.social|pssr", re.I), "pssr"),
    (re.compile(r"first.aid|cpr|efa", re.I), "efa"),
    (re.compile(r"survival.craft|pscrb", re.I), "pscrb"),
    (re.compile(r"medical.first.aid|mfa", re.I), "mfa"),
    (re.compile(r"medical.care\b|^mc$", re.I), "mc"),
    (re.compile(r"fast.rescue|frb", re.I), "frb"),
]


def _course_id_from_slug_and_type(slug: str, course_type: str) -> str | None:
    """Return normalised course_id by matching slug then course_type."""
    slug_lower = slug.lower()
    if "revalid" in slug_lower or "revalid" in course_type.lower():
        if "fire" in slug_lower or "fire" in course_type.lower():
            return "fpff"
        return "pst"
    if "advanced-firefight" in slug_lower or "advanced firefight" in course_type.lower():
        return "aff"
    if "basic-firefight" in slug_lower or "basic firefight" in course_type.lower():
        return "fpff"
    if "personal-survival" in slug_lower or "survival technique" in course_type.lower():
        return "pst"
    for pattern, cid in _COURSE_TYPE_MAP:
        if pattern.search(course_type) or pattern.search(slug_lower):
            return cid
    return None


class ResolveAcademyAdapter(BaseAdapter):
    """Fetch STCW course offerings from resolveacademy.com."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT

    def fetch(self, provider: dict) -> list[Offering]:
        """Return all future STCW course offerings found in static HTML."""
        offerings: list[Offering] = []
        seen: set[str] = set()
        now = datetime.now(timezone.utc).isoformat()

        for slug, default_course_id in _COURSE_PAGES:
            url = f"{BASE_URL}/course/{slug}/"
            try:
                resp = self._session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Resolve Academy: failed to fetch %s: %s", url, exc)
                time.sleep(2)
                continue

            time.sleep(2)

            page_offerings = self._parse_course_page(
                resp.text, url, slug, default_course_id, provider, now
            )
            for o in page_offerings:
                if o.id not in seen:
                    seen.add(o.id)
                    offerings.append(o)

        logger.info(
            "Resolve Academy adapter: %d offerings for provider %s",
            len(offerings),
            provider.get("id"),
        )
        return offerings

    def _parse_course_page(
        self,
        html_text: str,
        source_url: str,
        slug: str,
        default_course_id: str,
        provider: dict,
        now: str,
    ) -> list[Offering]:
        """Parse ``data-course`` JSON blobs from a single product page."""
        soup = BeautifulSoup(html_text, "lxml")
        offerings: list[Offering] = []

        for tag in soup.find_all("input", {"data-course": True}):
            raw = tag.get("data-course", "")
            # Skip JavaScript template fragments (not real JSON)
            if not raw.strip().startswith("{"):
                continue
            # Decode HTML entities before parsing JSON
            decoded = _html_mod.unescape(raw)
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                logger.debug(
                    "Resolve Academy: JSON parse error on %s: %s", slug, decoded[:80]
                )
                continue

            # Skip past events
            if data.get("past"):
                continue

            start_date: str | None = data.get("start")
            if not start_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date):
                continue

            # Use booking_end (last teaching day) as end date if available
            end_date: str | None = data.get("booking_end") or data.get("end") or start_date

            course_id = _course_id_from_slug_and_type(
                slug, data.get("course_type", "")
            ) or default_course_id

            # Duration from data payload
            duration_str: str = data.get("duration", "")
            duration_days: float | None = None
            m = re.match(r"(\d+(?:\.\d+)?)\s*day", duration_str, re.I)
            if m:
                duration_days = float(m.group(1))
            elif re.match(r"(\d+)\s*hour", duration_str, re.I):
                h = re.match(r"(\d+)", duration_str)
                if h:
                    duration_days = round(int(h.group(1)) / 8, 2)

            # Price
            price_raw = data.get("price")
            price: float | None = None
            if price_raw:
                try:
                    price = float(str(price_raw).replace(",", ""))
                except ValueError:
                    pass

            # Availability
            seat_count = data.get("seat_count")
            total_seats = data.get("total_seats")
            availability: str | None = None
            if seat_count is not None and total_seats is not None:
                try:
                    remaining = int(seat_count)
                    total = int(total_seats)
                    if remaining == 0:
                        availability = "sold_out"
                    elif remaining <= max(3, total // 4):
                        availability = "limited"
                    else:
                        availability = "available"
                except (ValueError, TypeError):
                    pass

            # Booking URL: add_to_cart links to WooCommerce cart
            add_to_cart = data.get("add_to_cart")
            booking_url: str | None = None
            if add_to_cart:
                booking_url = safe_url(
                    f"{BASE_URL}/cart/?add-to-cart={add_to_cart}"
                    f"&wc_bookings_field_start_date_year={start_date[:4]}"
                    f"&wc_bookings_field_start_date_month={start_date[5:7]}"
                    f"&wc_bookings_field_start_date_day={start_date[8:10]}"
                )

            course_url = safe_url(data.get("url_course") or source_url)

            offering_id = (
                f"{course_id}-resolve-academy-{start_date}-"
                f"{provider['id']}"
            )

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=end_date or start_date,
                    timezone="America/New_York",
                    duration_days=duration_days,
                    price=price,
                    currency="USD",
                    vat_included=False,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=booking_url,
                    source_url=course_url or source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
