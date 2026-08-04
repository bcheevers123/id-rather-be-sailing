"""Wavetrain Ltd adapter.

Scrapes the publicly listed course schedule at:
    https://www.wavetrain.co.uk/services/face-to-face

robots.txt (fetched 2026-08-04) blocks only specific third-party audit bots
(AhrefsBot, MJ12bot, dotbot, PetalBot, Zoominfobot, SiteAuditBot) — our
User-Agent string is fully allowed.

Page structure:
  The face-to-face page contains static HTML sections for each course type.
  Each section includes the course name in a heading (h2/h3), a list of
  scheduled dates, and optionally a price.  Dates appear in two formats:
    - Range:  "DD-DD Month YYYY"   (e.g. "13-16 April 2026")
    - Single: "DD Month YYYY"      (e.g. "28 April 2026")

Relevant course IDs:
    Ship Security Officer (SSO)                       → sso
    Proficiency in Designated Security Duties (PDSD)  → dsd

Courses listed on the page but outside our ID set (PFSO, CSO, PFSO Refresher,
Port State Control Officer) are silently skipped.

Booking URL is the contact page (https://www.wavetrain.co.uk/contact2.cfm)
as the site has no direct online booking system.
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

BASE_URL = "https://www.wavetrain.co.uk"
SOURCE_URL = f"{BASE_URL}/services/face-to-face"
BOOKING_URL = f"{BASE_URL}/contact2.cfm"

ADAPTER_SLUG = "wavetrain"

# ---------------------------------------------------------------------------
# Course ID inference — ordered, first match wins
# ---------------------------------------------------------------------------
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    # PDSD / Designated Security Duties
    (re.compile(r"designated.security.duties|[^a-z]pdsd[^a-z]", re.I), "dsd"),
    # SSO — avoid matching "PFSO" or "CSO" first
    (re.compile(r"ship.security.officer|[^a-z]sso[^a-z]", re.I), "sso"),
]


def _course_id_from_text(text: str) -> str | None:
    """Return the first matching canonical course_id, or None."""
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "13-16 April 2026" or "13 - 16 April 2026"
_DATE_RANGE_RE = re.compile(
    r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+(\d{4})\b",
    re.I,
)

# "28 April 2026"
_DATE_SINGLE_RE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"\s+(\d{4})\b",
    re.I,
)

# "02-04 December 2025 – 01-03 December 2026" style cross-year ranges (skip)
_DOUBLE_RANGE_RE = re.compile(
    r"\d{1,2}\s*[-–]\s*\d{1,2}\s+\w+\s+\d{4}\s*[-–]\s*\d{1,2}",
    re.I,
)


def _parse_dates(text: str) -> list[tuple[str, str]]:
    """Return a list of (start_iso, end_iso) tuples extracted from text."""
    results: list[tuple[str, str]] = []

    for m in _DATE_RANGE_RE.finditer(text):
        day_start = int(m.group(1))
        day_end = int(m.group(2))
        month = _MONTH_MAP.get(m.group(3).lower())
        year = int(m.group(4))
        if month is None:
            continue
        try:
            start_iso = datetime(year, month, day_start).date().isoformat()
            end_iso = datetime(year, month, day_end).date().isoformat()
            results.append((start_iso, end_iso))
        except ValueError:
            continue

    # Collect single dates not already captured by range matches
    range_positions = {m.start() for m in _DATE_RANGE_RE.finditer(text)}
    for m in _DATE_SINGLE_RE.finditer(text):
        # Skip if this single-date match overlaps a range match
        if any(m.start() >= rp and m.start() <= rp + 30 for rp in range_positions):
            continue
        day = int(m.group(1))
        month = _MONTH_MAP.get(m.group(2).lower())
        year = int(m.group(3))
        if month is None:
            continue
        try:
            iso = datetime(year, month, day).date().isoformat()
            results.append((iso, iso))
        except ValueError:
            continue

    return results


# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------
_PRICE_RE = re.compile(r"[£\xA3]([\d,]+(?:\.\d{2})?)")


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    """Return (price_float, vat_included) from text, or (None, None)."""
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    lower = text.lower()
    if "inc" in lower and "vat" in lower:
        vat_included = True
    elif ("ex" in lower or "+" in lower) and "vat" in lower:
        vat_included = False
    else:
        vat_included = None
    return price, vat_included


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class WavetrainAdapter(BaseAdapter):
    """Fetch STCW-adjacent course offerings from wavetrain.co.uk.

    Wavetrain specialises in maritime security training (SSO, PDSD/DSD)
    delivered aboard HMS Wellington in London.  Dates are listed on a single
    static HTML page; there is no API or booking widget.
    """

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(SOURCE_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("WavetrainAdapter: fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            offerings = self._parse(resp.text, provider)
        except Exception as exc:
            logger.warning("WavetrainAdapter: parse failed: %s", exc)
            return []

        logger.info("WavetrainAdapter: %d offerings extracted", len(offerings))
        return offerings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        """Parse course sections and emit one Offering per date per course."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        # Walk all heading tags (h1-h4) as section anchors.
        # For each heading whose text resolves to a known course_id, collect
        # all text until the next same-or-higher-level heading and look for
        # dates within that block.
        headings = soup.find_all(re.compile(r"^h[1-4]$"))

        for i, heading in enumerate(headings):
            heading_text = heading.get_text(" ", strip=True)
            course_id = _course_id_from_text(heading_text)
            if not course_id:
                continue

            # Gather the text content between this heading and the next
            section_parts: list[str] = [heading_text]
            sibling = heading.next_sibling
            while sibling:
                if hasattr(sibling, "name") and sibling.name and re.match(
                    r"^h[1-4]$", sibling.name
                ):
                    break
                if hasattr(sibling, "get_text"):
                    section_parts.append(sibling.get_text(" ", strip=True))
                elif isinstance(sibling, str):
                    section_parts.append(sibling)
                sibling = sibling.next_sibling

            section_text = " ".join(section_parts)
            price, vat_included = _extract_price(section_text)

            for start_date, end_date in _parse_dates(section_text):
                key = f"{course_id}:{start_date}"
                if key in seen:
                    continue
                seen.add(key)

                try:
                    dur = (
                        datetime.fromisoformat(end_date)
                        - datetime.fromisoformat(start_date)
                    ).days + 1
                except Exception:
                    dur = None

                offering_id = (
                    f"{provider['id']}-{ADAPTER_SLUG}-{course_id}-{start_date}"
                )

                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=end_date,
                        timezone="Europe/London",
                        duration_days=float(dur) if dur is not None else None,
                        price=price,
                        currency="GBP" if price is not None else None,
                        vat_included=vat_included,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(BOOKING_URL),
                        source_url=SOURCE_URL,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        # Fallback: if heading-based approach found nothing, try a full-page
        # scan by splitting on course-name boundaries.
        if not offerings:
            offerings = self._full_page_scan(soup, provider, now, seen)

        return offerings

    def _full_page_scan(
        self,
        soup: BeautifulSoup,
        provider: dict,
        now: str,
        seen: set[str],
    ) -> list[Offering]:
        """Fallback: scan full page text near SSO/PDSD keywords for dates."""
        full_text = soup.get_text(" ", strip=True)
        lines = [ln.strip() for ln in re.split(r"[\n\r]+", full_text) if ln.strip()]
        offerings: list[Offering] = []

        for i, line in enumerate(lines):
            course_id = _course_id_from_text(line)
            if not course_id:
                continue
            # Check ±8 lines for dates
            ctx = " ".join(lines[max(0, i - 2): i + 9])
            price, vat_included = _extract_price(ctx)

            for start_date, end_date in _parse_dates(ctx):
                key = f"{course_id}:{start_date}"
                if key in seen:
                    continue
                seen.add(key)

                try:
                    dur = (
                        datetime.fromisoformat(end_date)
                        - datetime.fromisoformat(start_date)
                    ).days + 1
                except Exception:
                    dur = None

                offering_id = (
                    f"{provider['id']}-{ADAPTER_SLUG}-{course_id}-{start_date}"
                )
                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=end_date,
                        timezone="Europe/London",
                        duration_days=float(dur) if dur is not None else None,
                        price=price,
                        currency="GBP" if price is not None else None,
                        vat_included=vat_included,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(BOOKING_URL),
                        source_url=SOURCE_URL,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        return offerings
