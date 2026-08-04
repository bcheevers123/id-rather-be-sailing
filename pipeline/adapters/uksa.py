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
USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

# Verified working URLs as of 2026-08.  FPFF (/course/fire-fighting-and-fire-prevention/)
# returns HTTP 404 — omitted until UKSA publishes a valid page.
COURSE_URLS = {
    "pst": "https://uksa.org/course/personal-survival-techniques/",
    "efa": "https://uksa.org/course/elementary-first-aid/",
    "mfa": "https://uksa.org/course/proficiency-in-medical-first-aid/",
}

# Match date strings like "04 Aug 2026" or "4 August 2026"
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")

# Strip £ and commas then parse price
_PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d+)?)")

_AVAILABILITY_MAP = {
    "sold out": "sold_out",
    "final places": "limited",
    "available": "available",
    "limited": "limited",
    "spaces available": "available",
}


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_availability(text: str) -> str | None:
    lower = text.lower().strip()
    for key, val in _AVAILABILITY_MAP.items():
        if key in lower:
            return val
    return None


class UKSAAdapter(BaseAdapter):
    def __init__(self, course_id: str):
        self.course_id = course_id
        self.source_url = COURSE_URLS.get(course_id, "https://uksa.org/courses/")

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        try:
            resp = session.get(self.source_url, timeout=45)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("UKSA fetch failed for %s: %s", self.source_url, e)
            return []
        time.sleep(2)
        try:
            return self._parse(resp.text, provider)
        except Exception as e:
            logger.warning("UKSA parse failed for %s: %s", self.source_url, e)
            return []

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()
        seen_dates: set[str] = set()

        # Strategy 1: structured table rows.
        # UKSA renders schedule as <table><tr> rows where the first cell contains
        # a date range like "04 Aug 2026 → 04 Aug 2026", subsequent cells hold
        # price, residential price, and availability text.
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            date_cell_text = cells[0].get_text(" ", strip=True)
            dates_found = _DATE_RE.findall(date_cell_text)
            if not dates_found:
                continue
            try:
                start_date = dateutil_parser.parse(dates_found[0], fuzzy=False).date().isoformat()
                end_date = (
                    dateutil_parser.parse(dates_found[1], fuzzy=False).date().isoformat()
                    if len(dates_found) > 1
                    else start_date
                )
            except Exception:
                continue

            if start_date in seen_dates:
                continue
            seen_dates.add(start_date)

            # Price: look through remaining cells for a £ value
            price: float | None = None
            for cell in cells[1:]:
                p = _parse_price(cell.get_text(" ", strip=True))
                if p is not None:
                    price = p
                    break

            # Availability: look for known status strings in all cells
            availability: str | None = None
            for cell in cells:
                a = _parse_availability(cell.get_text(" ", strip=True))
                if a is not None:
                    availability = a
                    break

            # Booking URL: prefer a "Book now" / "Add to Basket" link in the row
            booking: str | None = None
            for a_tag in row.find_all("a", href=True):
                href = a_tag["href"]
                if "cart" in href or "book" in href.lower() or "checkout" in href.lower():
                    booking = safe_url(href if href.startswith("http") else f"https://uksa.org{href}")
                    break
            if not booking:
                booking = safe_url(self.source_url)

            offerings.append(Offering(
                id=f"{self.course_id}-uksa-{start_date}",
                course_id=self.course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=end_date,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP",
                vat_included=False,
                delivery_format="in_person",
                availability=availability,
                booking_url=booking,
                source_url=self.source_url,
                last_verified=now,
                freshness_status="verified",
            ))

        # Strategy 2: fallback — scan all text for date patterns (no table structure found)
        if not offerings:
            for block in soup.find_all(string=_DATE_RE):
                text = block.strip()
                for match in _DATE_RE.finditer(text):
                    try:
                        d = dateutil_parser.parse(match.group(), fuzzy=False).date().isoformat()
                        if d in seen_dates:
                            continue
                        seen_dates.add(d)
                        offerings.append(Offering(
                            id=f"{self.course_id}-uksa-{d}",
                            course_id=self.course_id,
                            provider_id=provider["id"],
                            start_date=d,
                            end_date=d,
                            timezone="Europe/London",
                            duration_days=None,
                            price=None,
                            currency=None,
                            vat_included=None,
                            delivery_format="in_person",
                            availability=None,
                            booking_url=safe_url(self.source_url),
                            source_url=self.source_url,
                            last_verified=now,
                            freshness_status="verified",
                        ))
                    except Exception:
                        continue

        logger.info(
            "UKSA adapter extracted %d offerings from %s",
            len(offerings),
            self.source_url,
        )
        return offerings
