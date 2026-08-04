"""South West Maritime Academy (SWMA) adapter.

Scrapes the Arlo-powered upcoming-courses listing at southwestmaritimeacademy.com.

Page structure (confirmed by inspection):
  <ul class="arlo-list upcoming">
    <li class="arlo-group-divider ..."><h2>August 2026</h2></li>  ← month header
    <li class="arlo-cf ...">                                       ← course item
      ... date text, h4 title, price, arlo register/waiting-list link ...
    </li>
    ...
  </ul>

Pagination: /courses/upcoming/page/{n}/
Dates appear as "05 Aug" with the year carried from the preceding month header.
robots.txt only disallows /wp-admin/ — public pages are freely crawlable.
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

BASE_URL = "https://southwestmaritimeacademy.com"
UPCOMING_URL = f"{BASE_URL}/courses/upcoming/"
MAX_PAGES = 15  # safety limit; site currently has ~10 pages

# Maps keywords in course titles to normalised course IDs.
# Checked in order — first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention.*(fire.fight|ffff)|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"crowd.management|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"proficiency.in.fast.rescue|[^a-z]frb[^a-z]", re.I), "frb"),
]

# "05 Aug" or "5 Aug" (with or without leading zero), optionally followed by year
_DATE_RE = re.compile(r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", re.I)
# Year in group header e.g. "August 2026"
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
# Price e.g. "£125.00" or "£1,110.00"
_PRICE_RE = re.compile(r"£([\d,]+(?:\.\d{2})?)")

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


class SwMaritimeAdapter(BaseAdapter):
    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()

        for page_num in range(1, MAX_PAGES + 1):
            url = UPCOMING_URL if page_num == 1 else f"{UPCOMING_URL}page/{page_num}/"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("SWMA page %d fetch failed: %s", page_num, e)
                break
            time.sleep(2)

            try:
                offerings, has_more = self._parse_page(resp.text, url, provider, seen_ids)
            except Exception as e:
                logger.warning("SWMA page %d parse failed: %s", page_num, e)
                break

            all_offerings.extend(offerings)

            if not has_more:
                break

        logger.info("SWMA adapter: %d offerings total", len(all_offerings))
        return all_offerings

    def _parse_page(
        self,
        html: str,
        page_url: str,
        provider: dict,
        seen_ids: set[str],
    ) -> tuple[list[Offering], bool]:
        """Parse one paginated upcoming-courses page.

        Returns (offerings_found, has_more_pages).
        """
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        ul = soup.find("ul", class_="arlo-list")
        if not ul:
            return [], False

        items = ul.find_all("li", recursive=False)
        if not items:
            return [], False

        offerings: list[Offering] = []
        current_year: int = datetime.now().year  # updated as we hit month headers

        for li in items:
            classes = li.get("class", [])

            # Month/year group header — extract year
            if "arlo-group-divider" in classes:
                h = li.find(["h1", "h2", "h3", "h4"])
                if h:
                    ym = _YEAR_RE.search(h.get_text())
                    if ym:
                        current_year = int(ym.group(1))
                continue

            li_text = li.get_text(" ", strip=True)

            # Extract course title from heading link
            title_tag = li.find(["h3", "h4", "h5"])
            title = title_tag.get_text(" ", strip=True) if title_tag else ""
            if not title:
                # fallback: first anchor text
                a = li.find("a")
                title = a.get_text(" ", strip=True) if a else ""

            if not title:
                continue

            course_id = _course_id_from_text(title)
            if not course_id:
                continue

            # Extract start date
            dm = _DATE_RE.search(li_text)
            if not dm:
                continue
            day = int(dm.group(1))
            month = _MONTH_MAP[dm.group(2).lower()]
            try:
                start_date = datetime(current_year, month, day).date().isoformat()
            except ValueError:
                continue

            # Extract booking URL — prefer register link, fall back to waiting-list
            booking_url: str | None = None
            for a in li.find_all("a", href=True):
                href: str = a["href"]
                if "arlo.co/register" in href or "arlo.co/waiting-list" in href:
                    booking_url = href
                    if "register" in href:
                        break  # prefer register over waiting-list

            # Extract price
            price = _parse_price(li_text)
            vat_included: bool | None = None
            if price is not None:
                vat_included = "incl. vat" in li_text.lower() or "inc vat" in li_text.lower()

            # Availability hint
            availability: str | None = None
            low = li_text.lower()
            if "waiting list" in low or "sold out" in low or "full" in low:
                availability = "waiting_list"
            elif "register" in low or "available" in low:
                availability = "available"

            offering_id = f"{course_id}-swma-{start_date}"
            if offering_id in seen_ids:
                continue
            seen_ids.add(offering_id)

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=start_date,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP" if price is not None else None,
                    vat_included=vat_included,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=safe_url(booking_url) if booking_url else None,
                    source_url=page_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        # Check whether a next page exists
        pag = soup.find("div", class_="arlo-pagination")
        has_more = False
        if pag:
            next_links = pag.find_all("a", href=True)
            for a in next_links:
                if "next" in a.get_text(" ", strip=True).lower() or "›" in a.get_text():
                    has_more = True
                    break
            # Also check: if pagination has page numbers beyond current
            if not has_more:
                # Any link at all in pagination means more pages exist
                has_more = bool(next_links)

        return offerings, has_more
