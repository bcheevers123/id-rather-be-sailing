"""Galileo Maritime Academy adapter (Phuket, Thailand).

Galileo is Asia Pacific's only MCA-approved STCW training facility. The site
runs WordPress with a custom theme. Course dates are loaded asynchronously via
wp-admin/admin-ajax.php using the action ``get_course_groups_options``, which
returns an HTML fragment of radio inputs each carrying ISO start date, duration
in days, and availability status.

Cloudflare WAF: the site issues a JS challenge on all requests from data-centre
IPs. We use Playwright to load one course page (clearing the CF cookie), then
call the AJAX endpoint from within that page context — the browser already holds
the valid cf_clearance cookie so subsequent fetches succeed. This approach was
validated in Chrome DevTools on 2026-08-05.

MCA-approved course ID mapping (WordPress post ID -> normalised course ID)
  pst    — Personal Survival Techniques (PST)              [wp_id=956]
  pst    — STCW10 Basic Safety Training (bundle)            [wp_id=772]
  fpff   — Fire Fighting & Fire Prevention (FPFF)           [wp_id=938]
  efa    — Elementary First Aid (EFA)                       [wp_id=891]
  mc     — Medical Care (MC)                                [wp_id=1219]
  frb    — Fast Rescue Boat (FRB)                           [wp_id=1233]
  uaff   — Updating Advanced Fire Fighting (UAFF)           [wp_id=1520]
  upscrb — Updating Survival Craft & Rescue Boat (UPSCRB)   [wp_id=1230]
  ufrb   — Updating Fast Rescue Boat (UFRB)                 [wp_id=1236]

WP post IDs confirmed via data-course-id attributes 2026-08-05.
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

BASE_URL = "https://galileomaritimeacademy.com"
AJAX_URL = f"{BASE_URL}/wp-admin/admin-ajax.php"

# Hardcoded course table: (wordpress_post_id, normalised_course_id, course_url).
# Only MCA-approved courses. WP post IDs are stable across deploys.
_COURSE_TABLE: list[tuple[str, str, str]] = [
    # Basic STCW
    ("956",  "pst",    f"{BASE_URL}/course/personal-survival-techniques-pst/"),
    ("772",  "pst",    f"{BASE_URL}/course/stcw10-basic-safety-training/"),
    ("938",  "fpff",   f"{BASE_URL}/course/fire-fighting-amp-fire-prevention-fffp/"),
    ("891",  "efa",    f"{BASE_URL}/course/elementary-first-aid-efa/"),
    # Advanced STCW (MCA-approved subset)
    ("1219", "mc",     f"{BASE_URL}/course/medical-care-mc/"),
    ("1233", "frb",    f"{BASE_URL}/course/fast-rescue-boat-frb/"),
    # Refresher / Updating STCW
    ("1520", "uaff",   f"{BASE_URL}/course/updating-advanced-fire-fighting-uaff/"),
    ("1230", "upscrb", f"{BASE_URL}/course/updating-survival-craft-amp-rescue-boat-upscrb/"),
    ("1236", "ufrb",   f"{BASE_URL}/course/updating-fast-rescue-boat-ufrb/"),
]

_STATUS_MAP: dict[str, str] = {
    "confirmed": "available",
    "almost-full": "limited",
    "waitlist-open": "waitlist",
    "cancelled": "cancelled",
}

# Seed URL: load this first to obtain a valid Cloudflare clearance cookie.
_SEED_URL = f"{BASE_URL}/course/personal-survival-techniques-pst/"


class GalileoAdapter(BaseAdapter):
    """Adapter for Galileo Maritime Academy, Phuket, Thailand."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning(
                "playwright not installed — skipping Galileo. "
                "Install with: pip install playwright && python -m playwright install chromium"
            )
            return []

        provider_id = provider["id"]
        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                # Warm up: load one course page to clear the Cloudflare challenge.
                # The resulting cf_clearance cookie is held in the browser context
                # and sent automatically on all subsequent requests.
                logger.info("Galileo: loading seed page to satisfy Cloudflare...")
                try:
                    page.goto(_SEED_URL, timeout=60000, wait_until="networkidle")
                    page.wait_for_timeout(2000)
                except Exception as exc:
                    logger.warning("Galileo seed page load failed: %s", exc)
                    # Wait a bit extra in case a CF redirect is still in flight
                    page.wait_for_timeout(3000)

                # Call the AJAX endpoint for each course from within the page context.
                for wp_id, course_id, course_url in _COURSE_TABLE:
                    try:
                        result = page.evaluate(
                            """async ([ajaxUrl, wpId]) => {
                                const resp = await fetch(ajaxUrl, {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                    body: 'action=get_course_groups_options&course_id=' + wpId
                                })
                                return { status: resp.status, text: await resp.text() }
                            }""",
                            [AJAX_URL, wp_id],
                        )
                    except Exception as exc:
                        logger.warning("Galileo AJAX eval failed wp_id=%s: %s", wp_id, exc)
                        time.sleep(2)
                        continue

                    if result.get("status") != 200:
                        logger.warning(
                            "Galileo AJAX returned %s for wp_id=%s",
                            result.get("status"), wp_id,
                        )
                        time.sleep(2)
                        continue

                    try:
                        offerings = self._parse_groups(
                            result["text"],
                            course_id,
                            course_url,
                            provider_id,
                            seen_ids,
                        )
                        all_offerings.extend(offerings)
                    except Exception as exc:
                        logger.warning("Galileo parse failed wp_id=%s: %s", wp_id, exc)

                    time.sleep(1)

                browser.close()

        except Exception as exc:
            logger.error("Galileo adapter failed: %s", exc)

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
        seen: set[str] = set()
        if seen_ids is None:
            seen_ids = set()

        for inp in soup.find_all("input", attrs={"data-start": True}):
            start_iso = inp.get("data-start", "").strip()
            duration_str = inp.get("data-group-duration", "").strip()
            status_raw = inp.get("data-status", "confirmed").strip()
            if not start_iso:
                continue
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
