"""RT Training (Radio) adapter for marineradio.co.uk.

Site overview
-------------
marineradio.co.uk is a small static HTML site run by Kim Holt offering GMDSS
radio courses in the UK (currently Cornwall).  There is no robots.txt — the
path redirects to the homepage — so no scraping restrictions apply.

Schedule approach
-----------------
Each course has its own dedicated HTML page.  Dates (when listed) appear as
plain text inside a DATES section near the bottom of the page body.  The site
does not use a booking system or structured data; all information is embedded
in prose HTML.

Pages checked (as of 2026-08-04):
  - /gmdss-general-operators-certificate-goc.html   → has a date
  - /gmdss-long-range-certificate-lrc.html          → "CLOSED TILL FURTHER NOTICE"
  - /gmdss-restricted-operators-certificate-roc.html → DATES section empty
  - /caa-restricted-operators-certificate-of-competence-rocc-ocs.html → checked
  - /gmdss-refresher-oral-prepgoc-pre-study-course.html → checked

The adapter fetches each course page in turn, extracts any date ranges it can
parse, and returns an Offering per date.  Pages with no parseable dates are
silently skipped (no fabricated data is ever returned).

Course-ID mapping
-----------------
  goc  → gmdss-general-operators-certificate-goc.html
  lrc  → gmdss-long-range-certificate-lrc.html
  roc  → gmdss-restricted-operators-certificate-roc.html

Robustness
----------
The site is hand-crafted HTML with inconsistent capitalisation and spacing.
The date parser is intentionally permissive to handle formats like:
  "MARCH 2ND TO THE 9TH"   (year inferred from a nearby "DATES: YYYY" heading)
  "2 - 9 MARCH 2026"
  "2ND MARCH TO 9TH MARCH 2026"
If no parseable date is found the offering is omitted; the method always
returns a plain list (possibly empty).
"""

import logging
import re
import time
from calendar import month_abbr, month_name
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "http://www.marineradio.co.uk"

# Ordered list of (course_id, page_path, canonical_price_gbp_or_None)
# Prices taken from page text at time of writing; None means not listed.
_COURSE_PAGES: list[tuple[str, str, float | None]] = [
    ("goc", "/gmdss-general-operators-certificate-goc.html", 1480.0),
    ("lrc", "/gmdss-long-range-certificate-lrc.html", 460.0),
    ("roc", "/gmdss-restricted-operators-certificate-roc.html", None),
]

# Minimum delay in seconds between HTTP requests to the same domain
_REQUEST_DELAY = 2.0

# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

# Build a mapping from month name / abbreviated name → month number (1–12)
_MONTH_MAP: dict[str, int] = {}
for _i, _name in enumerate(month_name):
    if _name:
        _MONTH_MAP[_name.upper()] = _i
for _i, _abbr in enumerate(month_abbr):
    if _abbr:
        _MONTH_MAP[_abbr.upper()] = _i

# Ordinal suffixes to strip: 1st, 2nd, 3rd, 4th …
_ORDINAL_RE = re.compile(r"(\d+)(?:ST|ND|RD|TH)\b", re.I)

# Match a standalone 4-digit year
_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Patterns for "DD MONTH [YYYY]" or "MONTH DD [YYYY]"
_DATE_WORD_RE = re.compile(
    r"(?:(\d{1,2})\s+([A-Z]+)|([A-Z]+)\s+(\d{1,2}))"
    r"(?:\s+(20\d{2}))?",
    re.I,
)

# Range separator: "TO THE", "TO", " - ", "–"
_RANGE_SEP_RE = re.compile(r"\s+TO\s+THE\s+|\s+TO\s+|\s*[-–]\s*", re.I)


def _strip_ordinals(text: str) -> str:
    """Remove ordinal suffixes from day numbers: '2ND' → '2'."""
    return _ORDINAL_RE.sub(r"\1", text)


def _parse_single_date(text: str, fallback_year: int | None = None) -> date | None:
    """Try to parse a single date description into a date object."""
    text = _strip_ordinals(text.strip().upper())
    m = _DATE_WORD_RE.search(text)
    if not m:
        return None

    if m.group(1) and m.group(2):
        day_str, month_str = m.group(1), m.group(2)
    elif m.group(3) and m.group(4):
        month_str, day_str = m.group(3), m.group(4)
    else:
        return None

    month_num = _MONTH_MAP.get(month_str.upper())
    if not month_num:
        return None

    try:
        day = int(day_str)
    except ValueError:
        return None

    year_str = m.group(5)
    year = int(year_str) if year_str else fallback_year
    if not year:
        return None

    try:
        return date(year, month_num, day)
    except ValueError:
        return None


def _extract_year_from_heading(text: str) -> int | None:
    """Find the first 4-digit year in a DATES: heading, e.g. 'DATES: 2026'."""
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def _parse_date_range(
    section_text: str,
    fallback_year: int | None,
) -> tuple[date, date] | None:
    """
    Parse a date range from free-form text like:
      "MARCH 2ND TO THE 9TH"
      "2ND TO 9TH MARCH 2026"
      "2 - 9 MARCH 2026"

    Returns (start_date, end_date) or None if unparseable.
    """
    # Normalise text
    text = _strip_ordinals(section_text.strip().upper())

    # Try to find the range separator
    parts = _RANGE_SEP_RE.split(text, maxsplit=1)

    if len(parts) == 2:
        left, right = parts[0].strip(), parts[1].strip()
        # Parse end date first (more likely to have month/year context)
        end = _parse_single_date(right, fallback_year)
        if end:
            # Try to parse start using end's year and potentially month
            start = _parse_single_date(left, end.year)
            if not start:
                # left might be just a day number without month — borrow from right
                day_only = re.search(r"\b(\d{1,2})\b", left)
                if day_only:
                    try:
                        start = date(end.year, end.month, int(day_only.group(1)))
                    except ValueError:
                        pass
            if start:
                return (start, end)

    # Fallback: treat whole text as a single date (1-day course)
    single = _parse_single_date(text, fallback_year)
    if single:
        return (single, single)

    return None


def _extract_date_sections(page_text: str) -> list[tuple[date, date]]:
    """
    Scan page body text for DATES sections and extract date ranges.
    Returns a list of (start, end) tuples.
    """
    results: list[tuple[date, date]] = []

    # Split on 'DATES' keyword (case-insensitive)
    parts = re.split(r"\bDATES\b", page_text, flags=re.I)
    if len(parts) < 2:
        return results

    for chunk in parts[1:]:
        # Take up to ~200 chars after the DATES keyword
        snippet = chunk[:200]

        # Bail out on explicit closure notices
        if re.search(r"closed|no dates|contact us|no course", snippet, re.I):
            continue

        fallback_year = _extract_year_from_heading(snippet)

        # Split into lines and try each non-trivial line
        lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
        for line in lines:
            # Skip lines that are just a year or colons
            if re.fullmatch(r"[:\s\d]+", line):
                continue
            parsed = _parse_date_range(line, fallback_year)
            if parsed:
                results.append(parsed)
                break  # one range per DATES section

    return results


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class MarineRadioAdapter(BaseAdapter):
    """Scraper adapter for RT Training (Radio) at marineradio.co.uk.

    Fetches each course page, extracts date ranges from the DATES section,
    and returns one Offering per date range found.  Returns [] for any course
    page that has no parseable dates (e.g. 'CLOSED TILL FURTHER NOTICE').

    No robots.txt is present on the site (the path redirects to the homepage);
    no Disallow rules apply.  The adapter respects a 2-second minimum delay
    between requests.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        now = datetime.now(timezone.utc).isoformat()
        provider_id = provider.get("id", "unknown")
        offerings: list[Offering] = []
        first_request = True

        for course_id, page_path, price in _COURSE_PAGES:
            url = BASE_URL + page_path

            if not first_request:
                time.sleep(_REQUEST_DELAY)
            first_request = False

            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("MarineRadio: GET %s failed: %s", url, exc)
                continue

            try:
                soup = BeautifulSoup(resp.text, "lxml")
                page_text = soup.get_text(separator="\n")
            except Exception as exc:
                logger.warning("MarineRadio: parse error for %s: %s", url, exc)
                continue

            date_ranges = _extract_date_sections(page_text)
            if not date_ranges:
                logger.debug(
                    "MarineRadio: no parseable dates on %s for course %s",
                    url,
                    course_id,
                )
                continue

            for start_dt, end_dt in date_ranges:
                start_iso = start_dt.isoformat()
                end_iso = end_dt.isoformat()
                offering_id = (
                    f"{provider_id}-marineradio-{course_id}-{start_iso}"
                )
                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider_id,
                        start_date=start_iso,
                        end_date=end_iso,
                        timezone="Europe/London",
                        duration_days=float((end_dt - start_dt).days + 1),
                        price=price,
                        currency="GBP" if price is not None else None,
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(
                            BASE_URL + "/contact.html"
                        ),
                        source_url=url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        logger.info(
            "MarineRadioAdapter: %d offerings for provider %s",
            len(offerings),
            provider_id,
        )
        return offerings
