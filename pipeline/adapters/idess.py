"""IDESS Maritime Training Centre adapter.

Investigation findings (2026-08-04):
- Primary domain www.idess.com.ph does not resolve (DNS failure / site down).
- Fallback Weebly site idessmaritime.weebly.com is accessible but publishes
  NO course dates or schedule tables — only course titles and durations.
- The former booking system at www.idess.com.ph/booking/booking.php is
  unreachable.  Scheduling is done by direct contact.

This adapter tries both the primary domain and the Weebly fallback for any
date tables that may appear in future.  Until dates are published it returns
an empty list.

STCW page: https://idessmaritime.weebly.com/stcw-courses.html
Contact:   cda@idess.com.ph / idess.tad@idess.com.ph
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

# Try primary domain first; fall back to the Weebly mirror.
_CANDIDATE_URLS: list[str] = [
    "https://www.idess.com.ph/stcw",
    "https://www.idess.com.ph/courses",
    "https://www.idess.com.ph/schedule",
    "https://www.idess.com.ph/training-schedule",
    "https://idessmaritime.weebly.com/stcw-courses.html",
]

# Map keywords in page text / URL to normalised STCW course IDs.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# Accepts DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, and Month DD YYYY patterns.
_DATE_RE = re.compile(
    r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b"           # DD/MM/YYYY or DD-MM-YYYY
    r"|\b(\d{4}-\d{2}-\d{2})\b"                 # YYYY-MM-DD
    r"|(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\w*\.?\s+\d{1,2},?\s+\d{4}\b)",           # Month D YYYY
    re.I,
)
_SPACES_RE = re.compile(r"(\d+)")


def _parse_date(raw: str) -> str | None:
    """Return ISO YYYY-MM-DD or None for any recognised date string."""
    raw = raw.strip()
    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r"^(\d{2})[/-](\d{2})[/-](\d{4})$", raw)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            return None
    # YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", raw)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date().isoformat()
        except ValueError:
            return None
    # Month D YYYY
    for fmt in ("%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class IdessAdapter(BaseAdapter):
    """Adapter for IDESS Maritime Training Centre, Philippines.

    NOTE: as of investigation date 2026-08-04 the site publishes no
    structured schedule data.  The adapter will return [] until that changes.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        all_offerings: list[Offering] = []

        for url in _CANDIDATE_URLS:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.debug("IDESS: skipping %s — %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_page(resp.text, url, provider)
            except Exception as exc:
                logger.warning("IDESS: parse error for %s — %s", url, exc)
                continue

            if offerings:
                all_offerings.extend(offerings)

        if not all_offerings:
            logger.info(
                "IDESS adapter: 0 offerings — site unreachable or no dates published yet"
            )

        return all_offerings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_page(self, html: str, page_url: str, provider: dict) -> list[Offering]:
        """Scan any <table> rows on the page for date strings."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        # Determine course_id from page title or URL
        title_tag = soup.find("h1") or soup.find("h2") or soup.find("title")
        title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
        page_course_id = _course_id_from_text(title_text) or _course_id_from_text(page_url)

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            start_iso: str | None = None
            availability: str | None = None
            row_course_id: str | None = None

            for i, cell in enumerate(cells):
                cell_text = cell.get_text(" ", strip=True)

                # Try to pick up a per-row course name
                cid = _course_id_from_text(cell_text)
                if cid:
                    row_course_id = cid

                # Try to find a date
                m = _DATE_RE.search(cell_text)
                if m and start_iso is None:
                    raw_date = next(g for g in m.groups() if g)
                    start_iso = _parse_date(raw_date.strip())
                    # Next cell may hold available spaces
                    if start_iso and i + 1 < len(cells):
                        next_text = cells[i + 1].get_text(strip=True)
                        sm = _SPACES_RE.search(next_text)
                        if sm:
                            availability = f"{sm.group(1)} spaces"

            if not start_iso:
                continue

            course_id = row_course_id or page_course_id
            if not course_id:
                logger.debug("IDESS: no course_id for row with date %s at %s", start_iso, page_url)
                continue

            key = f"{course_id}-{start_iso}"
            if key in seen:
                continue
            seen.add(key)

            offerings.append(
                Offering(
                    id=f"{course_id}-idess-{start_iso}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=start_iso,
                    timezone="Asia/Manila",
                    duration_days=None,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=safe_url(page_url),
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
