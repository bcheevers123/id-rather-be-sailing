"""Maritime Institute of Technology and Graduate Studies (MITAGS) adapter.

Scrapes individual STCW/safety course pages on https://www.mitags.org for
session dates.  Each course page contains one or more "Available Dates -
<LOCATION>" h2 sections, each followed by a <form> (or sibling container)
with repeating groups of:
    Label "Course"     | value (course name)
    Label "Date"       | value "Mon DD YYYY to Mon DD YYYY"
    Label "Price"      | value "$X,XXX"
    "ADD TO CART" link

Date format on the page: "Sep 07 2026 to Sep 11 2026"
robots.txt:  Yoast block has `Disallow:` (empty — allows all).  No
             restriction on course pages.

Strategy:
  1. For each STCW course URL in COURSE_MAP, fetch the page.
  2. Parse all "Available Dates" sections.
  3. Extract start/end date pairs and optionally price.
  4. Emit one Offering per (course_id, location, start_date).
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

BASE_URL = "https://www.mitags.org"

# Maps normalised course IDs to their MITAGS course page URL slugs.
# Basic Training bundles PST + FPFF + EFA + PSSR — emit as "pst" (the
# primary STCW element); callers may fan-out if desired.
COURSE_MAP: list[tuple[str, str]] = [
    ("pst",   f"{BASE_URL}/course/basic-training/"),
    ("pst",   f"{BASE_URL}/course/personal-survival-techniques/"),
    ("fpff",  f"{BASE_URL}/course/basic-fire-fighting-16-hour/"),
    ("efa",   f"{BASE_URL}/course/first-aid-and-cpr/"),
    ("pssr",  f"{BASE_URL}/course/personal-safety-and-social-responsibilities/"),
    ("pscrb", f"{BASE_URL}/course/proficiency-in-survival-craft/"),
    ("pscrb", f"{BASE_URL}/course/proficiency-in-survival-craft-refresher/"),
    ("aff",   f"{BASE_URL}/course/advanced-firefighting-2/"),
    ("aff",   f"{BASE_URL}/course/advanced-fire-fighting-refresher/"),
    ("aff",   f"{BASE_URL}/course/advanced-fire-fighting-revalidation/"),
    ("mfa",   f"{BASE_URL}/course/medical-person-in-charge/"),
    ("mfa",   f"{BASE_URL}/course/medical-person-in-charge-refresher/"),
    ("mc",    f"{BASE_URL}/course/medical-care-provider/"),
]

# "Sep 07 2026 to Sep 11 2026" — both dates in the same format
_DATE_RANGE_RE = re.compile(
    r"([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})"
    r"\s+to\s+"
    r"([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})",
    re.I,
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "$2,155" or "$1,545" — optional, used for informational display
_PRICE_RE = re.compile(r"\$([0-9,]+)", re.I)


def _parse_date(month_abbr: str, day: str, year: str) -> str | None:
    """Return ISO date string or None on failure."""
    month = _MONTH_MAP.get(month_abbr.lower()[:3])
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day)).date().isoformat()
    except ValueError:
        return None


def _parse_price(text: str) -> float | None:
    """Return numeric price from '$2,155' style string, or None."""
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class MitagsAdapter(BaseAdapter):
    """Fetch STCW course offerings from www.mitags.org."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []
        seen: set[str] = set()

        for course_id, url in COURSE_MAP:
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("MITAGS: fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_course_page(
                    resp.text, url, course_id, provider, seen
                )
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning("MITAGS: parse failed %s: %s", url, e)

        logger.info("MITAGS adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _parse_course_page(
        self,
        html: str,
        page_url: str,
        course_id: str,
        provider: dict,
        seen: set[str],
    ) -> list[Offering]:
        """Extract session offerings from a single MITAGS course page.

        The page structure:
          <h2>Available Dates - BALTIMORE</h2>
          <form>
            ... repeated blocks of label+value rows:
            "Course" | <course name>
            "Date"   | "Sep 07 2026 to Sep 11 2026"
            "Price"  | "$2,155"
            <a>ADD TO CART</a>
          </form>
          <h2>Available Dates - SEATTLE</h2>
          ...
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []

        # Find all "Available Dates" h2/h3 headings
        for heading in soup.find_all(["h2", "h3"]):
            heading_text = heading.get_text(strip=True)
            if "available dates" not in heading_text.lower():
                continue

            # Determine location from heading text
            loc_upper = heading_text.upper()
            if "BALTIMORE" in loc_upper:
                location = "Baltimore"
            elif "SEATTLE" in loc_upper:
                location = "Seattle"
            elif "OFFSITE" in loc_upper:
                location = "Offsite"
            else:
                location = heading_text.replace("Available Dates", "").strip(" -").strip()

            # The session block is in a sibling element after this heading.
            # Walk siblings until we hit another h2/h3 or end of parent.
            container_text_blocks: list[str] = []
            sib = heading.find_next_sibling()
            while sib and sib.name not in ("h2", "h3"):
                container_text_blocks.append(sib.get_text(" ", strip=True))
                sib = sib.find_next_sibling()

            block_text = " ".join(container_text_blocks)

            # Extract all date ranges from this section
            for m in _DATE_RANGE_RE.finditer(block_text):
                start_date = _parse_date(m.group(1), m.group(2), m.group(3))
                end_date = _parse_date(m.group(4), m.group(5), m.group(6))
                if not start_date:
                    continue
                if not end_date:
                    end_date = start_date

                dedup_key = f"{course_id}-mitags-{start_date}-{location}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Try to find price near this date in the block text
                # Extract the region of text around this match
                match_start = m.start()
                context = block_text[max(0, match_start - 50): match_start + len(m.group(0)) + 100]
                price = _parse_price(context)

                offerings.append(
                    Offering(
                        id=dedup_key,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=end_date,
                        timezone="America/New_York",
                        duration_days=None,
                        price=price,
                        currency="USD" if price is not None else None,
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(page_url),
                        source_url=page_url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        if offerings:
            logger.info(
                "MITAGS: %d offerings for course_id=%s (%s)",
                len(offerings),
                course_id,
                page_url,
            )
        else:
            logger.debug("MITAGS: no sessions found at %s", page_url)

        return offerings
