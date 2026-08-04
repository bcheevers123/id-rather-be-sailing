"""Bluewater Yachting adapter.

Scrapes the Bluewater course schedule search page for STCW course dates.

URL pattern (server-rendered HTML, no JS required):
    https://www.bluewateryachting.com/crew-training/courses/search
        ?period=365&location_id=&course_id={id}

Table columns: DATE | COURSE | LOCATION | AVAILABILITY | (details button)

Bluewater operates from Antibes, Palma and Genoa and appears in MCA approval
PDFs as "Bluewater (Spain)" and "Bluewater (France)".  All 38 provider IDs
share this one website, so a single fetch call covers all locations; we use
provider["id"] on each Offering as-is.

Robots.txt allows all paths except /process and /app-view/ — the search page
is fully allowed.
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

BASE_URL = "https://www.bluewateryachting.com"
SEARCH_URL = f"{BASE_URL}/crew-training/courses/search"

# Maps Bluewater internal course_id (int) to our normalised course_id string.
# course_id=47 is the STCW Basic Safety Training package — it bundles PST,
# FPFF, EFA and PSSR; we emit all four so that searches on any component match.
_STCW_BUNDLE_COURSES = ["pst", "fpff", "efa", "pssr"]

_COURSE_MAP: dict[int, list[str]] = {
    47:  _STCW_BUNDLE_COURSES,          # STCW Basic Safety Training (bundle)
    79:  ["aff"],                        # Advanced Fire Fighting
    179: ["aff"],                        # Updated AFF
    82:  ["efa"],                        # Elementary First Aid
    50:  ["mfa"],                        # Proficiency in Medical First Aid
    51:  ["mc"],                         # Proficiency in Medical Care
    94:  ["mc"],                         # Updated Proficiency in Medical Care
    242: ["pscrb"],                      # Proficiency in Survival Craft & Rescue Boats
    180: ["pscrb"],                      # Updated PSCRB (Restricted)
}

# "05 October 2026" → ISO date
_DATE_RE = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})")

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_date(text: str) -> str | None:
    """Parse '05 October 2026' → '2026-10-05'. Returns None on failure."""
    m = _DATE_RE.search(text.strip())
    if not m:
        return None
    day, month_name, year = m.group(1), m.group(2).lower(), m.group(3)
    month = _MONTH_MAP.get(month_name)
    if month is None:
        return None
    try:
        return datetime(int(year), month, int(day)).date().isoformat()
    except ValueError:
        return None


class BluewaterAdapter(BaseAdapter):
    """Fetch STCW course offerings from bluewateryachting.com."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []

        for bw_course_id, course_ids in _COURSE_MAP.items():
            url = (
                f"{SEARCH_URL}?period=365&location_id=&course_id={bw_course_id}"
            )
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(
                    "Bluewater fetch failed for course_id=%s: %s", bw_course_id, e
                )
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                offerings = self._parse_search_page(
                    resp.text, url, provider, course_ids
                )
                all_offerings.extend(offerings)
            except Exception as e:
                logger.warning(
                    "Bluewater parse failed for course_id=%s: %s", bw_course_id, e
                )

        logger.info("Bluewater adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _parse_search_page(
        self,
        html: str,
        source_url: str,
        provider: dict,
        course_ids: list[str],
    ) -> list[Offering]:
        """Parse a /crew-training/courses/search results page."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []

        for row in soup.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            date_text = cells[0].get_text(strip=True)
            course_name = cells[1].get_text(strip=True)
            location_text = cells[2].get_text(strip=True)
            avail_text = cells[3].get_text(strip=True)

            # Skip online-only rows (date cell reads "Online")
            if date_text.lower() == "online":
                continue

            start_date = _parse_date(date_text)
            if not start_date:
                logger.debug("Bluewater: could not parse date %r", date_text)
                continue

            # Resolve the DETAILS link if present
            details_link: str | None = None
            for a in row.find_all("a", href=True):
                href = a["href"]
                if "/training-class/" in href and not href.endswith("#"):
                    details_link = href if href.startswith("http") else BASE_URL + href
                    break
            booking_url = safe_url(details_link or source_url)

            # Availability — "Available", "Fully booked", "Waiting list", etc.
            availability = avail_text if avail_text else None

            # Determine delivery format
            delivery_format = "online" if "online" in location_text.lower() else "in_person"

            # Emit one Offering per normalised course_id (bundle = 4 records)
            for course_id in course_ids:
                row_id = row.get("id", "")
                offering_id = f"{course_id}-bluewater-{start_date}-{row_id}" if row_id else f"{course_id}-bluewater-{start_date}"
                offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=start_date,
                        end_date=start_date,
                        timezone="UTC",
                        duration_days=None,
                        price=None,
                        currency=None,
                        vat_included=None,
                        delivery_format=delivery_format,
                        availability=availability,
                        booking_url=booking_url,
                        source_url=source_url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        return offerings
