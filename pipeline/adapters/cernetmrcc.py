"""CERNET MRCC adapter.

Scrapes https://www.cernetmrcc.com/calendario/ which lists GOC and ROC course
dates in a set of HTML tables, grouped by section heading.  LRC courses are
offered by arrangement only and are not listed in the calendar.

Page structure (Italian):
  <h4>CALENDARIO CORSI GOC 2026</h4>
  <table>
    <tr><th>Da</th><th>A</th><th>Durata</th></tr>
    <tr><td>Lunedì 12 Gennaio</td><td>Martedì 20 Gennaio</td><td>9 giorni</td></tr>
    ...
  </table>
  <h4>CALENDARIO CORSI ROC 2026</h4>
  <table>...</table>

Dates are expressed as Italian day-of-week + day-number + Italian month name,
without an explicit year; the year is extracted from the section heading.
No prices or booking URLs are published; contact is by phone/email only.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

CALENDAR_URL = "https://www.cernetmrcc.com/calendario/"

# Italian month names -> month number
_IT_MONTHS: dict[str, int] = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

# Section-heading keyword -> course_id
_HEADING_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bgoc\b", re.I), "goc"),
    (re.compile(r"\broc\b", re.I), "roc"),
    (re.compile(r"\blrc\b", re.I), "lrc"),
]

# Matches "Lunedì 12 Gennaio" or "12 Gennaio" (day-of-week is optional)
_IT_DATE_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-zÀ-ÿ]+)",
    re.I,
)

# Extract year from a heading string like "CALENDARIO CORSI GOC 2026"
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _parse_italian_date(raw: str, year: int) -> str | None:
    """Convert an Italian date string like 'Lunedì 12 Gennaio' to ISO YYYY-MM-DD.

    Returns None if parsing fails.
    """
    raw = raw.strip()
    m = _IT_DATE_RE.search(raw)
    if not m:
        return None
    day = int(m.group(1))
    month_name = m.group(2).lower()
    month = _IT_MONTHS.get(month_name)
    if month is None:
        return None
    try:
        return f"{year}-{month:02d}-{day:02d}"
    except Exception:
        return None


def _identify_course(heading: str) -> str | None:
    """Return canonical course_id from a section heading, or None."""
    for pattern, course_id in _HEADING_COURSE_MAP:
        if pattern.search(heading):
            return course_id
    return None


class CernetmrccAdapter(BaseAdapter):
    """Adapter for CERNET MRCC (https://www.cernetmrcc.com/)."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(CALENDAR_URL, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("CernetMRCC calendar fetch failed: %s", exc)
            return []

        time.sleep(2)

        try:
            offerings = _parse_calendar(resp.text, provider)
        except Exception as exc:
            logger.warning("CernetMRCC calendar parse failed: %s", exc)
            return []

        logger.info(
            "CernetMRCC adapter extracted %d offerings for provider %s",
            len(offerings),
            provider.get("id"),
        )
        return offerings


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_calendar(html: str, provider: dict) -> list[Offering]:
    """Parse the calendario page and return all Offering objects."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    # Walk every element in document order.  When we see an h-tag that
    # identifies a course section, remember the course_id + year.  When we
    # see a <table> after such a heading, parse its rows.
    current_course_id: str | None = None
    current_year: int = datetime.now(timezone.utc).year

    for element in soup.find_all(True):
        tag_name = element.name

        # Detect section headings (h2–h5)
        if tag_name in ("h2", "h3", "h4", "h5"):
            heading_text = element.get_text(" ", strip=True)
            cid = _identify_course(heading_text)
            if cid is not None:
                current_course_id = cid
                year_m = _YEAR_RE.search(heading_text)
                if year_m:
                    current_year = int(year_m.group(1))
            continue

        # Parse tables under a known course section
        if tag_name == "table" and current_course_id is not None:
            rows = element.find_all("tr")
            for row in rows:
                cells = [
                    td.get_text(" ", strip=True)
                    for td in row.find_all(["td", "th"])
                ]
                if len(cells) < 2:
                    continue

                # Skip header rows
                joined = " ".join(cells).lower()
                if "da" in joined and ("a" in joined or "durata" in joined):
                    # Likely the header row; check if first cell is purely "Da"
                    if cells[0].strip().lower() in ("da", "from", "inizio", "start"):
                        continue

                start_raw = cells[0]
                end_raw = cells[1]

                # Skip rows that look like break notices ("Pausa Estiva" etc.)
                if not _IT_DATE_RE.search(start_raw):
                    continue

                start_d = _parse_italian_date(start_raw, current_year)
                end_d = _parse_italian_date(end_raw, current_year)

                if not start_d:
                    continue
                if not end_d:
                    end_d = start_d

                offering_id = (
                    f"{provider['id']}-cernetmrcc-{current_course_id}-{start_d}"
                )
                if offering_id in seen:
                    continue
                seen.add(offering_id)

                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=current_course_id,
                        provider_id=provider["id"],
                        start_date=start_d,
                        end_date=end_d,
                        timezone="Europe/Rome",
                        duration_days=_parse_duration(cells[2] if len(cells) > 2 else ""),
                        price=None,
                        currency=None,
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(CALENDAR_URL),
                        source_url=CALENDAR_URL,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

    return offerings


def _parse_duration(raw: str) -> float | None:
    """Parse Italian duration strings like '9 giorni' into a float number of days."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*giorn", raw, re.I)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None
