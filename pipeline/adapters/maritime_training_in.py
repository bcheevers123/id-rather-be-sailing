"""Anglo-Eastern Maritime Training Centre (AEMTC) – maritimetraining.in adapter.

Scrapes the public course-schedule at:
  https://www.maritimetraining.in/schedule.php?fromdate=YYYY-MM-DD&todate=YYYY-MM-DD
  with pagination via &start=10&start=20 …

HTML structure (static server-rendered, no JS required):
    <tr>
      <td>Course Name</td>
      <td>Duration</td>
      <td>3rd August 2026</td>   ← Start Date
      <td>7th August 2026</td>   ← End Date
      <td>Mumbai</td>
      <td><a href="…more-info…">More Info</a><a href="course_booking.php?…">Apply</a></td>
    </tr>

Date format: ordinal day + month-name + 4-digit year  ("3rd August 2026").
Pagination:  schedule.php?start=0, start=10, start=20 … until a page returns
             fewer than 10 data rows (or zero).
"""

import logging
import re
import time
from datetime import datetime, timezone, date
from calendar import month_abbr

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.maritimetraining.in"
SCHEDULE_URL = f"{BASE_URL}/schedule.php"

# How far ahead to look (months from now)
_MONTHS_AHEAD = 6
_PAGE_SIZE = 10

# Maps regex patterns against course title to normalised course IDs.
# Ordered: first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques?\b|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.and.fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.and.social.responsibility|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care.on.board|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
    # combined / individual labelled courses
    (re.compile(r"basic.safety.training", re.I), "pst"),  # catch-all BST → pst
]

# Ordinal-day date: "3rd August 2026", "14th September 2026"
_DATE_RE = re.compile(
    r"(\d{1,2})(?:st|nd|rd|th)\s+([A-Za-z]+)\s+(\d{4})"
)

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"]
)}


def _parse_date(text: str) -> str | None:
    """Parse ordinal-day date string to ISO-8601 YYYY-MM-DD or None."""
    m = _DATE_RE.search(text.strip())
    if not m:
        return None
    day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    month_num = _MONTHS.get(month_name)
    if not month_num:
        return None
    try:
        return date(year, month_num, day).isoformat()
    except ValueError:
        return None


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class MaritimeTrainingInAdapter(BaseAdapter):
    """Adapter for Anglo-Eastern Maritime Training Centre (AEMTC), India."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        today = date.today()
        # Cover current month through 6 months ahead
        from_date = date(today.year, today.month, 1)
        # End date: first day of month 6 months ahead, last day of that month
        end_month = today.month + _MONTHS_AHEAD
        end_year = today.year + (end_month - 1) // 12
        end_month = ((end_month - 1) % 12) + 1
        import calendar as _cal
        to_date = date(end_year, end_month, _cal.monthrange(end_year, end_month)[1])

        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()

        start = 0
        while True:
            url = (
                f"{SCHEDULE_URL}"
                f"?start={start}"
                f"&fromdate={from_date.isoformat()}"
                f"&todate={to_date.isoformat()}"
                f"&category=&cokeywords=&location="
            )
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("maritimetraining.in fetch failed (%s): %s", url, exc)
                return all_offerings

            time.sleep(2)

            try:
                rows = self._parse_page(resp.text, url, provider)
            except Exception as exc:
                logger.warning("maritimetraining.in parse failed (%s): %s", url, exc)
                return all_offerings

            # Deduplicate
            new_count = 0
            for o in rows:
                if o.id not in seen_ids:
                    seen_ids.add(o.id)
                    all_offerings.append(o)
                    new_count += 1

            logger.debug(
                "maritimetraining.in page start=%d: %d rows, %d new",
                start, len(rows), new_count,
            )

            # Stop if we got fewer rows than a full page (last page)
            if len(rows) < _PAGE_SIZE:
                break

            start += _PAGE_SIZE

        logger.info(
            "maritimetraining.in adapter: %d STCW offerings for provider=%s",
            len(all_offerings),
            provider.get("id"),
        )
        return all_offerings

    def _parse_page(self, html: str, page_url: str, provider: dict) -> list[Offering]:
        """Parse one schedule page and return STCW offerings."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue

            course_name = cells[0].get_text(" ", strip=True)

            # Skip nav / sidebar / footer rows
            if not course_name or len(course_name) < 8:
                continue
            if any(kw in course_name for kw in ("HOME |", "All Courses\n", "Home  |")):
                continue

            start_text = cells[2].get_text(strip=True)
            end_text = cells[3].get_text(strip=True)

            # Must have a parseable start date
            start_iso = _parse_date(start_text)
            if not start_iso:
                continue

            end_iso = _parse_date(end_text) or start_iso
            location = cells[4].get_text(strip=True) if len(cells) > 4 else None

            # Match to a known STCW course ID
            course_id = _course_id_from_text(course_name)
            if not course_id:
                continue

            # Extract booking URL from last cell links
            booking_url: str | None = None
            more_info_url: str | None = None
            if len(cells) > 5:
                links = cells[5].find_all("a", href=True)
            else:
                links = row.find_all("a", href=True)
            for a in links:
                href = a["href"]
                if not href.startswith("http"):
                    href = BASE_URL + "/" + href.lstrip("/")
                if "booking" in href or "apply" in href.lower():
                    booking_url = safe_url(href)
                elif more_info_url is None:
                    more_info_url = safe_url(href)

            source_url = more_info_url or page_url

            offering_id = f"{course_id}-aemtc-{start_iso}-{location or 'in'}".lower().replace(" ", "-")

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_iso,
                    end_date=end_iso,
                    timezone="Asia/Kolkata",
                    duration_days=None,
                    price=None,
                    currency=None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=booking_url,
                    source_url=source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        return offerings
