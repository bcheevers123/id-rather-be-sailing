"""Palma Sea School adapter (Palma de Mallorca, Spain).

Palma Sea School runs a WordPress/WooCommerce site. STCW courses are sold as
WooCommerce variable products where each variation represents a specific
course date. Course dates appear in a ``<select>`` dropdown labelled "Course
Dates" on each product page.

robots.txt: allows all crawlers; admin-ajax.php is explicitly allowed.
No crawl-delay directive is present; we use a 2-second minimum between requests.

Courses offered (as of scouting 2026-08):
  efa   — Elementary First Aid                           €199
  aff   — Updated Proficiency in Advanced Fire Fighting  €200
  pssr  — Personal Safety & Social Responsibility        (stock varies)
  pst   — Personal Survival Techniques                   (stock varies)

The FPFF (Fire Prevention & Fire Fighting) course links to the contact page
rather than a bookable product and is excluded until it has its own page.

Course URL table: (normalised_course_id, product_url, price_eur)
Prices are used only as a fallback; the page-level price is preferred.
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

BASE_URL = "https://www.palmaseaschool.com"

# Hardcoded course table: (course_id, url).
# Populated from product-sitemap.xml and manual scouting.
_COURSE_TABLE: list[tuple[str, str]] = [
    ("efa",  f"{BASE_URL}/courses/stcw-courses/elementary-first-aid/"),
    ("pst",  f"{BASE_URL}/courses/stcw-courses/stcw-personal-survival-techniques-sea-survival/"),
    ("pssr", f"{BASE_URL}/courses/stcw-courses/personal-safety-social-responsibilities/"),
    ("aff",  f"{BASE_URL}/courses/stcw-courses/advanced-fire-fighting-update/"),
]

# Regex to match dates like "11 August 2026", "03 August 2026", "14 December 2026"
# Also handles "05 - 07 August 2026" style multi-day labels (uses first date as start).
_DATE_RE = re.compile(
    r"(\d{1,2})\s*(?:-\s*(\d{1,2}))?\s+([A-Za-z]+)\s+(\d{4})"
)

# WooCommerce embeds variation data as HTML-entity-encoded JSON in a <script> tag.
# The price appears as: &quot;display_price&quot;:199 (HTML-encoded) or
# "display_price":199 (decoded).  We match both forms.
_PRICE_RE = re.compile(
    r'(?:&quot;|")display_price(?:&quot;|")\s*:\s*([\d]+(?:\.\d+)?)'
)


def _parse_date_option(text: str) -> tuple[str, str] | None:
    """Parse a dropdown option text into (start_iso, end_iso).

    Returns None if the text cannot be parsed as a real date (e.g. placeholder
    text like "Please email to request dates").
    """
    m = _DATE_RE.search(text)
    if not m:
        return None

    start_day = int(m.group(1))
    end_day = int(m.group(2)) if m.group(2) else start_day
    month_str = m.group(3)
    year_str = m.group(4)

    try:
        start_d = dateutil_parser.parse(
            f"{start_day} {month_str} {year_str}", fuzzy=False
        ).date().isoformat()
        end_d = dateutil_parser.parse(
            f"{end_day} {month_str} {year_str}", fuzzy=False
        ).date().isoformat()
    except Exception:
        logger.debug("PalmaSea: could not parse date from %r", text)
        return None

    return start_d, end_d


def _parse_price(html_text: str) -> float | None:
    """Extract price from WooCommerce JSON embedded in the page.

    WooCommerce writes variation data as JSON containing ``"display_price":199``
    in a <script> tag. We use the first match which corresponds to the product
    price (all variations share the same base price on this site).
    """
    m = _PRICE_RE.search(html_text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except (ValueError, TypeError):
        return None


def _parse_course_page(
    html: str,
    course_id: str,
    source_url: str,
    provider_id: str,
) -> list[Offering]:
    """Parse a WooCommerce product page and return Offering objects.

    Dates come from a <select> dropdown (variation attribute or custom field).
    Each <option> whose text matches a date pattern becomes one offering.
    Out-of-stock pages may have no <select> at all — we skip gracefully.
    """
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()

    # Detect out-of-stock before spending time parsing
    page_text = soup.get_text(" ", strip=True)
    out_of_stock = "out of stock" in page_text.lower()

    # Extract price from the raw HTML (WooCommerce JSON is HTML-entity-encoded)
    price = _parse_price(html)

    offerings: list[Offering] = []
    seen_starts: set[str] = set()

    # WooCommerce variation selects are <select> elements; the course-date
    # dropdown may also be a plain custom attribute select.
    for select in soup.find_all("select"):
        for option in select.find_all("option"):
            option_text = option.get_text(strip=True)
            if not option_text:
                continue

            parsed = _parse_date_option(option_text)
            if parsed is None:
                continue

            start_d, end_d = parsed

            if start_d in seen_starts:
                continue
            seen_starts.add(start_d)

            # Infer duration_days from start/end
            try:
                s = datetime.fromisoformat(start_d)
                e = datetime.fromisoformat(end_d)
                duration_days: float | None = float((e - s).days + 1)
            except Exception:
                duration_days = None

            offerings.append(
                Offering(
                    id=f"{course_id}-palma-sea-{start_d}",
                    course_id=course_id,
                    provider_id=provider_id,
                    start_date=start_d,
                    end_date=end_d,
                    timezone="Europe/Madrid",
                    duration_days=duration_days,
                    price=price,
                    currency="EUR",
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None if not out_of_stock else "unavailable",
                    booking_url=safe_url(source_url),
                    source_url=source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

    if not offerings and not out_of_stock:
        logger.debug(
            "PalmaSea: no date options found for course_id=%s url=%s",
            course_id,
            source_url,
        )

    return offerings


class PalmaSeaAdapter(BaseAdapter):
    """Adapter for Palma Sea School, Palma de Mallorca, Spain."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        provider_id = provider["id"]
        all_offerings: list[Offering] = []

        for course_id, url in _COURSE_TABLE:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "PalmaSea: fetch failed course_id=%s url=%s: %s",
                    course_id, url, exc,
                )
                time.sleep(2)
                continue

            time.sleep(2)

            try:
                offerings = _parse_course_page(
                    resp.text, course_id, url, provider_id
                )
                all_offerings.extend(offerings)
                logger.debug(
                    "PalmaSea: %d offerings for course_id=%s",
                    len(offerings), course_id,
                )
            except Exception as exc:
                logger.warning(
                    "PalmaSea: parse failed course_id=%s: %s", course_id, exc
                )

        logger.info(
            "PalmaSea adapter: %d offerings across %d courses",
            len(all_offerings),
            len(_COURSE_TABLE),
        )
        return all_offerings
