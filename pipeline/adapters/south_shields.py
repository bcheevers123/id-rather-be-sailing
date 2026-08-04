"""South Shields Marine School (Tyne Coast College MOST) adapter.

Scrapes course dates from the EBSonTrack booking system at
ebsontrackprospect-live.tynecoast.ac.uk, which the SSMS course pages link to
via "Apply now" buttons.

The EBSonTrack ProspectusList page renders all table rows in the initial HTML
response (DataTables pagination is CSS-only, not AJAX), so a plain
requests.get() retrieves every record for a given topic code without needing
JavaScript execution.

Table columns (by data-column / position):
    DESCRIPTION      – course name
    DISPLAY_FULL     – "Spaces" or "Full" (availability)
    LOCATION         – venue name
    DAY              – day of week
    START_DATE_STRING – DD/MM/YYYY
    WEEKS            – duration in weeks
    Adult Fee        – price with £ prefix
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

_EBS_BASE = (
    "https://ebsontrackprospect-live.tynecoast.ac.uk/Page/ProspectusList"
    "?search_TOPIC_operator=Equals&search_TOPIC_type=String&search_TOPIC_value={}"
)

# Mapping from our course_id to the EBSonTrack TOPIC code used in the
# Apply-now URL on each SSMS course page.
_COURSE_TOPICS: list[tuple[str, str]] = [
    ("pst",   "PST"),
    ("fpff",  "FPFFF"),
    ("efa",   "EFA"),
    ("pssr",  "PSSR"),
    ("pscrb", "PSCRB"),
    ("aff",   "AFF"),
    ("mfa",   "MCASR"),   # Medical First Aid
    ("mc",    "MCAS"),    # Medical Care Aboard Ship
]

# Booking URL per course_id (the SSMS course page, not EBS)
_BOOKING_URLS: dict[str, str] = {
    "pst":   "https://www.southshieldsmarineschool.com/course/personal-survival-techniques/",
    "fpff":  "https://www.southshieldsmarineschool.com/course/fire-prevention-and-firefighting/",
    "efa":   "https://www.southshieldsmarineschool.com/course/elementary-first-aid-efa/",
    "pssr":  "https://www.southshieldsmarineschool.com/course/personal-safety-and-social-responsibility/",
    "pscrb": "https://www.southshieldsmarineschool.com/course/proficiency-in-survival-craft-and-rescue-boats/",
    "aff":   "https://www.southshieldsmarineschool.com/course/advanced-firefighting/",
    "mfa":   "https://www.southshieldsmarineschool.com/course/medical-first-aid-onboard-ship/",
    "mc":    "https://www.southshieldsmarineschool.com/course/medical-care-aboard-ship/",
}

_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
# Match £ or replacement-character variants that appear when encoding is
# mis-detected, then capture the decimal number that follows.
_PRICE_RE = re.compile(r"[£\xef\xbf\xbd�]?\s*([\d,]+\.\d{2})")


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class SouthShieldsAdapter(BaseAdapter):
    """Fetches STCW course dates from South Shields Marine School via EBSonTrack."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        for course_id, topic_code in _COURSE_TOPICS:
            url = _EBS_BASE.format(topic_code)
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "SouthShields fetch failed [%s/%s]: %s", course_id, topic_code, exc
                )
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                # Force UTF-8 decoding — the server returns UTF-8 but requests
                # may detect a different charset from Content-Type.
                html = resp.content.decode("utf-8", errors="replace")
                offerings = self._parse_table(
                    html, url, course_id, provider, now
                )
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning(
                    "SouthShields parse failed [%s/%s]: %s", course_id, topic_code, exc
                )

        logger.info(
            "SouthShields adapter: %d offerings for provider %s",
            len(all_offerings),
            provider["id"],
        )
        return all_offerings

    def _parse_table(
        self,
        html: str,
        source_url: str,
        course_id: str,
        provider: dict,
        now: str,
    ) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            logger.debug("SouthShields: no table found at %s", source_url)
            return []

        # Resolve column indices from thead headers (data-column attribute)
        col_index: dict[str, int] = {}
        for i, th in enumerate(table.find("thead").find_all("th")):
            col_name = th.get("data-column", "").strip()
            if col_name:
                col_index[col_name] = i

        offerings: list[Offering] = []
        seen_dates: set[str] = set()
        booking_url = safe_url(_BOOKING_URLS.get(course_id, source_url))

        tbody = table.find("tbody")
        if not tbody:
            return []

        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue

            def cell_text(col: str) -> str:
                idx = col_index.get(col)
                if idx is None or idx >= len(cells):
                    return ""
                return cells[idx].get_text(strip=True)

            date_str = cell_text("START_DATE_STRING")
            m = _DATE_RE.search(date_str)
            if not m:
                continue

            try:
                start_date = datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat()
            except ValueError:
                continue

            if start_date in seen_dates:
                continue
            seen_dates.add(start_date)

            availability_raw = cell_text("DISPLAY_FULL").strip()
            availability = availability_raw if availability_raw else None

            # Duration: WEEKS column holds integer weeks
            weeks_text = cell_text("WEEKS")
            duration_days: float | None = None
            if weeks_text:
                try:
                    duration_days = float(weeks_text) * 7
                except ValueError:
                    pass

            # Price: Adult Fee column (data-column="TOTALFEE")
            adult_fee_text = cell_text("TOTALFEE")
            price = _parse_price(adult_fee_text)

            offerings.append(
                Offering(
                    id=f"{course_id}-south-shields-{start_date}",
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=start_date,
                    timezone="Europe/London",
                    duration_days=duration_days,
                    price=price,
                    currency="GBP" if price is not None else None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=booking_url,
                    source_url=source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "SouthShields: %d offerings for course_id=%s", len(offerings), course_id
        )
        return offerings
