"""Seahaven Maritime Academy adapter.

Scrapes the course listing at seahavenmaritimeacademy.co.uk/courses-all/ to
discover STCW / basic-training course pages, then scrapes each course page for
date-based booking blocks.

Booking blocks have the form:
    Mon 17 Aug
    Monday 17-21 August 2026
    Newhaven
    £825.00 incl. VAT
    Register

The STCW basic training package (PST + FPFF + EFA + PSSR bundle) is mapped to
course_id='pst'.
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

BASE = "https://seahavenmaritimeacademy.co.uk"
LISTING_URL = "https://seahavenmaritimeacademy.co.uk/courses-all/"

# Match the long date string: "Monday 17-21 August 2026" or "Monday 17 August 2026"
# Group 1 = start day number, Group 2 = optional end day number,
# Group 3 = month name, Group 4 = year
_DATE_RANGE_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"\s+(\d{1,2})(?:-(\d{1,2}))?"
    r"\s+([A-Za-z]+)"
    r"\s+(\d{4})",
    re.I,
)

# Match price like "£825.00 incl. VAT" or "£825"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")


class SeahavenAdapter(BaseAdapter):
    def __init__(self):
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: get the course listing to find STCW course URLs
        try:
            resp = session.get(LISTING_URL, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Seahaven listing fetch failed: %s", e)
            return []

        time.sleep(2)

        try:
            course_urls = _extract_course_urls(resp.text)
        except Exception as e:
            logger.warning("Seahaven listing parse failed: %s", e)
            return []

        if not course_urls:
            logger.warning("Seahaven: no STCW course URLs found on listing page")
            return []

        # Step 2: scrape each discovered course page
        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        for url in course_urls:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Seahaven course fetch failed %s: %s", url, e)
                time.sleep(2)
                continue

            time.sleep(2)

            try:
                page_offerings = _parse_course_page(
                    resp.text, url, provider, seen_dates
                )
                offerings.extend(page_offerings)
            except Exception as e:
                logger.warning("Seahaven course parse failed %s: %s", url, e)

        logger.info("Seahaven adapter: %d offerings extracted", len(offerings))
        return offerings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_course_urls(html: str) -> list[str]:
    """Return unique absolute URLs for STCW / basic-training course pages."""
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        lower = href.lower()
        if "stcw" in lower or "basic-training" in lower:
            if href.startswith("http"):
                abs_url = href
            elif href.startswith("/"):
                abs_url = BASE + href
            else:
                continue
            if abs_url not in seen:
                seen.add(abs_url)
                urls.append(abs_url)

    return urls


def _parse_course_page(
    html: str,
    source_url: str,
    provider: dict,
    seen_dates: set[str],
) -> list[Offering]:
    """Parse a single course page and return Offering objects."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []

    # Walk the full text block-by-block looking for the long date string.
    # Each booking block contains the date string and a price near it.
    # We search the entire page text but anchor price extraction to the
    # nearest surrounding container element.
    full_text = soup.get_text(" ", strip=True)

    # Find all date-range matches in page text
    for m in _DATE_RANGE_RE.finditer(full_text):
        start_day = int(m.group(1))
        end_day = int(m.group(2)) if m.group(2) else start_day
        month = m.group(3)
        year = m.group(4)

        start_str = f"{start_day} {month} {year}"
        end_str = f"{end_day} {month} {year}"

        try:
            start_d = dateutil_parser.parse(start_str, fuzzy=False).date().isoformat()
            end_d = dateutil_parser.parse(end_str, fuzzy=False).date().isoformat()
        except Exception:
            continue

        if start_d in seen_dates:
            continue
        seen_dates.add(start_d)

        # Extract price from context around the match
        ctx_start = max(0, m.start() - 200)
        ctx_end = min(len(full_text), m.end() + 300)
        context = full_text[ctx_start:ctx_end]
        price, vat_included = _extract_price(context)

        offering_id = f"pst-seahaven-{start_d}"

        offerings.append(
            Offering(
                id=offering_id,
                course_id="pst",
                provider_id=provider["id"],
                start_date=start_d,
                end_date=end_d,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP",
                vat_included=vat_included,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(source_url),
                source_url=source_url,
                last_verified=now,
                freshness_status="verified",
            )
        )

    return offerings


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    """Return (price_float, vat_included) from a text snippet."""
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    text_lower = text.lower()
    if "incl" in text_lower and "vat" in text_lower:
        vat_included = True
    elif "excl" in text_lower and "vat" in text_lower:
        vat_included = False
    else:
        vat_included = None
    return price, vat_included
