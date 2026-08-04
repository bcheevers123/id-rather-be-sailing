"""Seefunkschule Dipl.-Ing. Koblmiller adapter (Ebreichsdorf/Wien/Attersee, Austria).

This is a small family-run school offering GMDSS / SRC / LRC / Amateurfunk
courses. The site runs plain static HTML served via Apache over HTTP only —
the HTTPS cert is misconfigured (it resolves to webmail.webfish.at, not the
school domain), so all requests use ``http://seefunkschule.at/``.

robots.txt: no robots.txt file is present on the server; Apache returns 404,
which by convention means no restrictions. We comply with a 2-second minimum
delay between requests.

Schedule page: ``http://seefunkschule.at/termine.htm``
  Plain HTML, one ``<table>`` per course session, with the course type in the
  left cell and a block of German date text in the right cell. Example:

    <td>SRC + Wetter</td>
    <td>Beginn:30.Jannuar 2026 ... SRC: 30./31. Jannuar 2026 ...</td>

Course ID mapping (only these two appear on the schedule page):
  SRC (Kurzbereichsfunk) -> roc   (Short Range Certificate = ROC equivalent)
  LRC (Langbereichsfunk) -> lrc   (Long Range Certificate)

All other entries (RYA Yachtmaster, Amateurfunk, KI) are not in our
normalised course_id set and are skipped.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

# HTTP only — the HTTPS cert points to a different host (webmail.webfish.at)
BASE_URL = "http://seefunkschule.at"
SCHEDULE_URL = f"{BASE_URL}/termine.htm"
BOOKING_URL = f"{BASE_URL}/termine.htm"

ADAPTER_SLUG = "seefunkschule"

# Course name fragments → normalised course ID
# SRC (Seefunk Kurzbereich) ≈ Short Range Certificate (ROC)
# LRC (Seefunk Langbereich) ≈ Long Range Certificate
_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bSRC\b", re.I), "roc"),
    (re.compile(r"\bLRC\b", re.I), "lrc"),
]

# German month names (including Koblmiller's misspelling "Jannuar")
_DE_MONTHS = {
    "jänner": "January", "jannuar": "January", "januar": "January",
    "februar": "February",
    "märz": "March", "marz": "March",
    "april": "April",
    "mai": "May",
    "juni": "June",
    "juli": "July",
    "august": "August",
    "september": "September",
    "oktober": "October",
    "november": "November",
    "dezember": "December",
}

# Patterns for German date text such as:
#   "3. bis 6. April 2026"        → start 3 Apr, end 6 Apr
#   "30./31. Jannuar 2026"         → start 30 Jan, end 31 Jan
#   "13./14. Februar 2026"         → start 13 Feb, end 14 Feb
#   "10./11. + 17./18. + 24./25. Jannuar 2026"  → first pair only
_RANGE_DOT_RE = re.compile(
    r"(\d{1,2})\./(\d{1,2})\.\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})"
)
_RANGE_BIS_RE = re.compile(
    r"(\d{1,2})\.\s+bis\s+(\d{1,2})\.\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})"
)
_SINGLE_DATE_RE = re.compile(
    r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s+(\d{4})"
)
# "Beginn: 10. Jannuar 2026" — used to capture start date
_BEGINN_RE = re.compile(
    r"Beginn\s*:\s*(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s*_?\s*(\d{4})",
    re.I,
)


def _normalise_month(german: str) -> str:
    """Translate a German (or misspelled) month name to English."""
    return _DE_MONTHS.get(german.lower(), german)


def _parse_de_date(day: str, month: str, year: str) -> str | None:
    """Parse day/month(german)/year into ISO date string."""
    try:
        en_month = _normalise_month(month)
        return dateutil_parser.parse(f"{day} {en_month} {year}").date().isoformat()
    except Exception:
        return None


_RANGE_BIS_NOYEAR_RE = re.compile(
    r"(\d{1,2})\.\s+bis\s+(\d{1,2})\.\s+([A-Za-zÄÖÜäöüß]+)(?!\s+\d{4})"
)
_YEAR_RE = re.compile(r"\b(20\d\d)\b")


def _extract_dates(text: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) from German date text.

    Tries various patterns; falls back to single-date match.
    """
    # Extract any 4-digit year present anywhere in the text (used as fallback)
    year_m = _YEAR_RE.search(text)
    fallback_year = year_m.group(1) if year_m else None

    # Pattern: "3. bis 6. April 2026" (with explicit year)
    m = _RANGE_BIS_RE.search(text)
    if m:
        start = _parse_de_date(m.group(1), m.group(3), m.group(4))
        end = _parse_de_date(m.group(2), m.group(3), m.group(4))
        if start:
            return start, end or start

    # Pattern: "3. bis 6. April" (year missing — use fallback year from context)
    if fallback_year:
        m = _RANGE_BIS_NOYEAR_RE.search(text)
        if m:
            start = _parse_de_date(m.group(1), m.group(3), fallback_year)
            end = _parse_de_date(m.group(2), m.group(3), fallback_year)
            if start:
                return start, end or start

    # Pattern: "30./31. Jannuar 2026"
    m = _RANGE_DOT_RE.search(text)
    if m:
        start = _parse_de_date(m.group(1), m.group(3), m.group(4))
        end = _parse_de_date(m.group(2), m.group(3), m.group(4))
        if start:
            return start, end or start

    # Single date: "Beginn: 10. Jannuar 2026"
    m = _BEGINN_RE.search(text)
    if m:
        start = _parse_de_date(m.group(1), m.group(2), m.group(3))
        if start:
            return start, start

    # Last resort: first date-like token
    m = _SINGLE_DATE_RE.search(text)
    if m:
        start = _parse_de_date(m.group(1), m.group(2), m.group(3))
        if start:
            return start, start

    return None, None


def _course_id_from_text(text: str) -> str | None:
    for pattern, cid in _COURSE_MAP:
        if pattern.search(text):
            return cid
    return None


class SeefunkschuleAdapter(BaseAdapter):
    """Scrape GMDSS course dates from Seefunkschule Dipl.-Ing. Koblmiller."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(SCHEDULE_URL, timeout=20)
            resp.raise_for_status()
            # Honour the declared charset (ISO-8859-1)
            resp.encoding = resp.apparent_encoding or "iso-8859-1"
        except Exception as exc:
            logger.warning("Seefunkschule fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            return self._parse(resp.text, provider)
        except Exception as exc:
            logger.warning("Seefunkschule parse failed: %s", exc)
            return []

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()
        provider_id = provider["id"]
        seen: set[str] = set()

        # Each course session is wrapped in a 2-column <table border="2">
        # Left cell: course type label (may contain links like "SRC", "LRC")
        # Right cell: date block beginning with "Beginn: ..."
        for table in soup.find_all("table", attrs={"border": "2"}):
            rows = table.find_all("tr")
            if not rows:
                continue
            row = rows[0]
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            left_text = cells[0].get_text(" ", strip=True)
            right_text = cells[1].get_text(" ", strip=True)
            # Merge both cells for course-type detection
            full_text = f"{left_text} {right_text}"

            course_id = _course_id_from_text(left_text) or _course_id_from_text(full_text)
            if not course_id:
                logger.debug(
                    "Seefunkschule: no recognised course in: %s", left_text[:80]
                )
                continue

            start_date, end_date = _extract_dates(right_text)
            if not start_date:
                logger.debug(
                    "Seefunkschule: could not parse date from: %s", right_text[:120]
                )
                continue

            offering_id = (
                f"{provider_id}-{ADAPTER_SLUG}-{course_id}-{start_date}"
            )[:80]

            if offering_id in seen:
                continue
            seen.add(offering_id)

            # Compute duration_days
            try:
                from datetime import date
                d1 = date.fromisoformat(start_date)
                d2 = date.fromisoformat(end_date or start_date)
                duration_days = float((d2 - d1).days + 1)
            except Exception:
                duration_days = None

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider_id,
                    start_date=start_date,
                    end_date=end_date or start_date,
                    timezone="Europe/Vienna",
                    duration_days=duration_days,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(BOOKING_URL),
                    source_url=SCHEDULE_URL,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "Seefunkschule adapter: %d offerings for provider %s",
            len(offerings),
            provider_id,
        )
        return offerings
