"""Adapter for DDRC Healthcare / Devon and Cornwall (ddrc.org).

Scrapes STCW maritime medical course schedule pages. DDRC uses a standard
WordPress + Arlo booking integration. Each course has a dedicated schedule
page on ddrc.org listing upcoming sessions with dates, prices, availability,
and direct Arlo registration links.

Robots.txt: allow all / crawl-delay 10 s.  We use a 10-second delay between
requests to comply with the declared crawl-delay.

STCW courses offered (scouted 2026-08-04):
  MFA  https://www.ddrc.org/training/courses/11-stcw-mca-proficiency-in-medical-first-aid/region-UK/
         £575.00 incl. VAT, 4 days (Mon-Thu)
  MC   https://www.ddrc.org/training/courses/12-stcw-mca-certificate-of-proficiency-in-medical-care/region-UK/
         £750.00 incl. VAT, 5 days (Mon-Fri)
  EFA  https://www.ddrc.org/training/courses/60-stcw-mca-elementary-first-aid/region-UK/
         £140.00 incl. VAT, 1 day  (no current dates at time of scouting)

Note: DDRC does not appear to offer PST, FPFF, PSSR, PSCRB, AFF, or FRB.
The "Medical Care Refresher" (course 13) is a refresher/revalidation rather
than the initial MC certification; it is mapped to course_id="mc" with a
note in the offering id to avoid confusion with the full MC course.
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
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

# Crawl-delay declared in robots.txt.
_CRAWL_DELAY = 10

_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")

# Arlo registration link pattern.
_ARLO_HREF_RE = re.compile(r"arlo\.co.*register", re.I)

# Availability text patterns (Arlo uses "N places" or "N place remaining").
_PLACES_RE = re.compile(r"(\d+)\s+place", re.I)

# Schedule pages indexed by course_id.
# Tuple: (url, duration_days)
_COURSE_PAGES: dict[str, tuple[str, int | None]] = {
    "mfa": (
        "https://www.ddrc.org/training/courses/11-stcw-mca-proficiency-in-medical-first-aid/region-UK/",
        4,
    ),
    "mc": (
        "https://www.ddrc.org/training/courses/12-stcw-mca-certificate-of-proficiency-in-medical-care/region-UK/",
        5,
    ),
    "efa": (
        "https://www.ddrc.org/training/courses/60-stcw-mca-elementary-first-aid/region-UK/",
        1,
    ),
}


class DDRCAdapter(BaseAdapter):
    """Fetches STCW course dates from DDRC Healthcare (ddrc.org).

    Uses requests + BeautifulSoup to scrape Arlo-powered course schedule
    pages.  Each session block contains a date, price (incl. VAT), places
    remaining, and a direct Arlo booking link.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        offerings: list[Offering] = []

        for course_id, (url, duration_days) in _COURSE_PAGES.items():
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("DDRC fetch failed %s: %s", url, e)
                time.sleep(_CRAWL_DELAY)
                continue

            time.sleep(_CRAWL_DELAY)

            try:
                page_offerings = _parse_course_page(
                    resp.text,
                    source_url=url,
                    course_id=course_id,
                    duration_days=duration_days,
                    provider=provider,
                )
                offerings.extend(page_offerings)
            except Exception as e:
                logger.warning("DDRC parse failed %s: %s", url, e)

        logger.info("DDRC adapter: %d offerings extracted", len(offerings))
        return offerings


# ---------------------------------------------------------------------------
# Parsing helpers (module-level for testability)
# ---------------------------------------------------------------------------

def _parse_course_page(
    html: str,
    source_url: str,
    course_id: str,
    duration_days: int | None,
    provider: dict,
) -> list[Offering]:
    """Extract Offering objects from a single DDRC course schedule page."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    # DDRC/Arlo renders each session as a block containing:
    #   - a date element (strong tag or span with date text)
    #   - a price element
    #   - availability text ("N places")
    #   - a registration link to ddrc.arlo.co

    # Strategy 1: look for Arlo-style event containers.
    # Each session is wrapped in an <li> or <div> that contains a booking link.
    containers = _find_session_containers(soup)

    for container in containers:
        text = container.get_text(" ", strip=True)

        # Extract start date — first well-formed date in the container.
        start_date = _extract_first_date(container)
        if not start_date:
            continue
        if start_date in seen:
            continue
        seen.add(start_date)

        # Compute end date from duration.
        end_date = _compute_end_date(start_date, duration_days)

        # Price
        price, vat_included = _extract_price(text)

        # Availability
        availability = _extract_availability(text)

        # Booking URL — prefer the Arlo registration link.
        booking_url = _extract_booking_url(container) or safe_url(source_url)

        offerings.append(
            Offering(
                id=f"{course_id}-ddrc-{start_date}",
                course_id=course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=end_date,
                timezone="Europe/London",
                duration_days=float(duration_days) if duration_days else None,
                price=price,
                currency="GBP" if price is not None else None,
                vat_included=vat_included,
                delivery_format="in_person",
                availability=availability,
                booking_url=booking_url,
                source_url=source_url,
                last_verified=now,
                freshness_status="verified",
            )
        )

    # Strategy 2: fallback — scan the whole page for date patterns if no
    # containers were found (e.g. site redesign).
    if not offerings:
        offerings = _fallback_date_scan(soup, source_url, course_id, duration_days, provider, now)

    logger.info(
        "DDRC: %d offerings from %s (%s)", len(offerings), source_url, course_id
    )
    return offerings


def _find_session_containers(soup: BeautifulSoup):
    """Return elements that likely represent individual course session blocks.

    DDRC's Arlo integration wraps each session in an <li> containing a
    registration link pointing to ddrc.arlo.co.  We collect those <li>
    elements first; fall back to <div> elements if none found.
    """
    containers = [
        li for li in soup.find_all("li")
        if li.find("a", href=_ARLO_HREF_RE)
    ]
    if containers:
        return containers

    containers = [
        div for div in soup.find_all("div")
        if div.find("a", href=_ARLO_HREF_RE)
    ]
    return containers


def _extract_first_date(container) -> str | None:
    """Return the first parseable ISO date string found in a container."""
    text = container.get_text(" ", strip=True)
    # Look for patterns like "24 Aug 2026", "24 August 2026", "14 Sep 2026" etc.
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", text)
    if m:
        try:
            return dateutil_parser.parse(m.group(0), fuzzy=False).date().isoformat()
        except Exception:
            pass
    # Broader fuzzy fallback
    try:
        return dateutil_parser.parse(text, fuzzy=True).date().isoformat()
    except Exception:
        return None


def _compute_end_date(start_iso: str, duration_days: int | None) -> str:
    """Return end date ISO string given start and duration."""
    if not duration_days or duration_days <= 1:
        return start_iso
    from datetime import date, timedelta
    try:
        start = date.fromisoformat(start_iso)
        return (start + timedelta(days=duration_days - 1)).isoformat()
    except Exception:
        return start_iso


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    """Return (price_float, vat_included) from a text block."""
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None

    lower = text.lower()
    if "incl" in lower and "vat" in lower:
        vat_included = True
    elif "excl" in lower and "vat" in lower:
        vat_included = False
    else:
        vat_included = None

    return price, vat_included


def _extract_availability(text: str) -> str | None:
    """Return availability string, e.g. '5 places', or None."""
    m = _PLACES_RE.search(text)
    if m:
        n = int(m.group(1))
        if n == 0:
            return "sold_out"
        if n <= 3:
            return "limited"
        return "available"
    lower = text.lower()
    if "sold out" in lower or "full" in lower:
        return "sold_out"
    return None


def _extract_booking_url(container) -> str | None:
    """Return the Arlo registration URL from the session container."""
    link = container.find("a", href=_ARLO_HREF_RE)
    if link:
        return safe_url(link.get("href"))
    return None


def _fallback_date_scan(
    soup: BeautifulSoup,
    source_url: str,
    course_id: str,
    duration_days: int | None,
    provider: dict,
    now: str,
) -> list[Offering]:
    """Scan whole page for date patterns when container detection fails."""
    offerings: list[Offering] = []
    seen: set[str] = set()
    date_re = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")

    for m in date_re.finditer(soup.get_text(" ", strip=True)):
        try:
            d = dateutil_parser.parse(m.group(0), fuzzy=False).date().isoformat()
        except Exception:
            continue
        if d in seen:
            continue
        seen.add(d)
        end_date = _compute_end_date(d, duration_days)
        offerings.append(
            Offering(
                id=f"{course_id}-ddrc-{d}",
                course_id=course_id,
                provider_id=provider["id"],
                start_date=d,
                end_date=end_date,
                timezone="Europe/London",
                duration_days=float(duration_days) if duration_days else None,
                price=None,
                currency=None,
                vat_included=None,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(source_url),
                source_url=source_url,
                last_verified=now,
                freshness_status="verified",
            )
        )
    return offerings
