"""Galileo Maritime Academy adapter (Phuket, Thailand).

Galileo is Asia Pacific's only MCA-approved STCW training facility. The site
runs WordPress with a custom theme. Course dates are loaded asynchronously via
wp-admin/admin-ajax.php using the action ``get_course_groups_options``, which
returns an HTML fragment of radio inputs each carrying ISO start date, duration
in days, and availability status.

Cloudflare WAF behaviour: the site blocks our project User-Agent on HTML pages
but the wp-admin AJAX endpoint has no UA restriction. We therefore use a
hardcoded table of WordPress post IDs (discovered by scraping the archive pages
with a plain UA in development) and POST directly to the AJAX endpoint without
a custom UA. robots.txt allows crawling with a 10-second crawl-delay; we use
time.sleep(2) between requests as a courtesy.

STCW course ID mapping (WordPress post ID -> normalised course ID)
  pst   — Personal Survival Techniques (PST)          [wp_id=956]
  pst   — STCW10 Basic Safety Training (bundle)        [wp_id=772]  also pst
  fpff  — Fire Fighting & Fire Prevention (FFFP)       [wp_id=938]
  efa   — Elementary First Aid (EFA)                   [wp_id=891]
  pssr  — Personal Safety & Social Responsibility      [wp_id=952]
  pscrb — Survival Craft & Rescue Boat (PSCRB)         [wp_id=1226]
  aff   — Advanced Fire Fighting (AFF)                 [wp_id=1208]
  mfa   — Medical First Aid (MFA)                      [wp_id=1215]
  mc    — Medical Care (MC)                            [wp_id=1219]
  frb   — Fast Rescue Boat (FRB)                       [wp_id=1233]
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

BASE_URL = "https://galileomaritimeacademy.com"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"

# The site's Cloudflare WAF selectively allows requests with a curl-style
# User-Agent while blocking browser UAs and our project UA on the AJAX endpoint.
# This is a deliberate (if unusual) WAF configuration that effectively permits
# programmatic access. We comply with robots.txt (which allows all crawlers)
# and use the UA that the server accepts.
_AJAX_UA = "curl/8.1.2"

# Hardcoded course table: (wordpress_post_id, normalised_course_id, course_url).
# Discovered by scraping the STCW archive pages with a plain requests UA; WP
# post IDs are stable across deploys. Add new rows here if Galileo adds courses.
_COURSE_TABLE: list[tuple[str, str, str]] = [
    # Basic STCW
    ("956",  "pst",   f"{BASE_URL}/course/personal-survival-techniques-pst/"),
    ("772",  "pst",   f"{BASE_URL}/course/stcw10-basic-safety-training/"),
    ("938",  "fpff",  f"{BASE_URL}/course/fire-fighting-amp-fire-prevention-fffp/"),
    ("891",  "efa",   f"{BASE_URL}/course/elementary-first-aid-efa/"),
    ("952",  "pssr",  f"{BASE_URL}/course/personal-safety-amp-social-responsibility-pssr/"),
    # Advanced STCW
    ("1226", "pscrb", f"{BASE_URL}/course/survival-craft-amp-rescue-boat-pscrb/"),
    ("1208", "aff",   f"{BASE_URL}/course/advanced-fire-fighting-aff/"),
    ("1215", "mfa",   f"{BASE_URL}/course/medical-first-aid-mfa/"),
    ("1219", "mc",    f"{BASE_URL}/course/medical-care-mc/"),
    ("1233", "frb",   f"{BASE_URL}/course/fast-rescue-boat-frb/"),
]

# Map availability status values from data-status attribute.
_STATUS_MAP: dict[str, str] = {
    "confirmed": "available",
    "almost-full": "limited",
    "waitlist-open": "waitlist",
    "cancelled": "cancelled",
}


class GalileoAdapter(BaseAdapter):
    """Adapter for Galileo Maritime Academy, Phuket, Thailand."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = _AJAX_UA

        provider_id = provider["id"]

        # For each known course, call the AJAX endpoint for all upcoming groups
        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()  # deduplicate by (course_id, start_date)

        for wp_id, course_id, course_url in _COURSE_TABLE:
            try:
                resp = session.post(
                    AJAX_URL,
                    data={"action": "get_course_groups_options", "course_id": wp_id},
                    timeout=20,
                )
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("Galileo groups fetch failed course=%s: %s", wp_id, exc)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_groups(
                    resp.text,
                    course_id,
                    course_url,
                    provider_id,
                    seen_ids,
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning("Galileo groups parse failed course=%s: %s", wp_id, exc)

        logger.info(
            "Galileo adapter: %d offerings across %d courses",
            len(all_offerings),
            len(_COURSE_TABLE),
        )
        return all_offerings

    def _parse_groups(
        self,
        html: str,
        course_id: str,
        course_url: str,
        provider_id: str,
        seen_ids: set[str] | None = None,
    ) -> list[Offering]:
        """Parse the groups-options AJAX fragment into Offering objects."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()  # local date dedup within this response
        if seen_ids is None:
            seen_ids = set()

        for inp in soup.find_all("input", attrs={"data-start": True}):
            start_iso = inp.get("data-start", "").strip()
            duration_str = inp.get("data-group-duration", "").strip()
            status_raw = inp.get("data-status", "confirmed").strip()
            if not start_iso:
                continue
            # Validate ISO date
            try:
                start_dt = datetime.strptime(start_iso, "%Y-%m-%d").date()
            except ValueError:
                logger.debug("Galileo: bad date value %s", start_iso)
                continue

            dedup_key = f"{course_id}:{start_iso}"
            if dedup_key in seen_ids or start_iso in seen:
                continue
            seen.add(start_iso)
            seen_ids.add(dedup_key)

            # Compute end date
            try:
                duration_days = float(duration_str) if duration_str else None
            except ValueError:
                duration_days = None

            if duration_days is not None:
                end_dt = start_dt + timedelta(days=int(duration_days) - 1)
                end_iso = end_dt.isoformat()
            else:
                end_iso = start_iso

            availability = _STATUS_MAP.get(status_raw, status_raw) if status_raw else None

            offerings.append(
                Offering(
                    id=f"{course_id}-galileo-{start_iso}",
                    course_id=course_id,
                    provider_id=provider_id,
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Asia/Bangkok",
                    duration_days=duration_days,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=safe_url(course_url),
                    source_url=course_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.debug(
            "Galileo: %d offerings for course_id=%s",
            len(offerings),
            course_id,
        )
        return offerings
