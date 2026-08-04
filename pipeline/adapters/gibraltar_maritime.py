"""University of Gibraltar / Gibraltar Maritime Academy adapter.

Scrapes the non-academic STCW short-course pages at unigib.edu.gi.

All dates on the site are published as "TBD – Please enquire".  The adapter
therefore records each course as a single offering with an empty start_date
and freshness_status="enquire", so the pipeline knows the provider is active
but that no specific run date is available yet.

Course pages scraped (from non-academic-courses-sitemap.xml):
  - Personal Survival Techniques (PST)
  - Personal Survival Techniques Refresher (PST)
  - Elementary First Aid (EFA)
  - Fire Prevention and Firefighting (FPFF)
  - Fire Prevention and Firefighting Refresher (FPFF)
  - Personal Safety and Social Responsibility (PSSR)
  - Proficiency in Maritime Security Awareness (pssr-adjacent, mapped to pssr)
  - STCW Basic Safety Training Week (bundle – yields pst/fpff/efa/pssr)
  - MCA Accredited STCW Tanker Fire Fighting (aff)
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

BASE_URL = "https://www.unigib.edu.gi"

# Known STCW/maritime short-course pages with their normalised course IDs.
# The STCW Basic Safety Training Week bundles four individual STCW components;
# we emit one offering per component so all four appear in search results.
_COURSE_PAGES: list[tuple[str, list[str]]] = [
    (
        "/professional-development-courses/short-courses/personal-survival-techniques/",
        ["pst"],
    ),
    (
        "/professional-development-courses/short-courses/personal-survival-techniques-refresher-training/",
        ["pst"],
    ),
    (
        "/professional-development-courses/short-courses/elementary-first-aid/",
        ["efa"],
    ),
    (
        "/professional-development-courses/short-courses/fire-prevention-and-firefighting/",
        ["fpff"],
    ),
    (
        "/professional-development-courses/short-courses/fire-prevention-and-firefighting-refresher-training/",
        ["fpff"],
    ),
    (
        "/professional-development-courses/short-courses/personal-safety-and-social-responsibility/",
        ["pssr"],
    ),
    (
        "/professional-development-courses/short-courses/proficiency-in-maritime-security-awareness/",
        ["pssr"],
    ),
    (
        "/professional-development-courses/short-courses/mca-accredited-stcw-tanker-fire-fighting/",
        ["aff"],
    ),
    # The Basic Safety Training Week bundles PST + FPFF + EFA + PSSR
    (
        "/professional-development-courses/short-courses/stcw-basic-safety-training-week/",
        ["pst", "fpff", "efa", "pssr"],
    ),
]

# Match fee patterns like "£165", "£ 950", "£610.00"
_PRICE_RE = re.compile(r"£\s*(\d[\d,]*(?:\.\d{1,2})?)")

# Match duration expressed as "X Day", "X.X Days", "X/2 day" etc.
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*day", re.I)


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_duration(text: str) -> float | None:
    m = _DURATION_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


class GibraltarMaritimeAdapter(BaseAdapter):
    """Adapter for University of Gibraltar maritime / STCW short courses."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        # The site requires a convincing browser fingerprint; bare requests
        # User-Agent returns 403 from nginx.
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-GB,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": (
                    '"Google Chrome";v="125", "Chromium";v="125", '
                    '"Not.A/Brand";v="24"'
                ),
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        now = datetime.now(timezone.utc).isoformat()
        all_offerings: list[Offering] = []

        for path, course_ids in _COURSE_PAGES:
            url = BASE_URL + path
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("GibraltarMaritime fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                page_text = BeautifulSoup(resp.text, "lxml").get_text(" ", strip=True)
                price = _parse_price(page_text)
                duration = _parse_duration(page_text)
            except Exception as e:
                logger.warning("GibraltarMaritime parse failed %s: %s", url, e)
                continue

            for course_id in course_ids:
                offering_id = f"{course_id}-gibraltar-maritime-{path.strip('/').split('/')[-1]}"
                all_offerings.append(
                    Offering(
                        id=offering_id,
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date="",
                        end_date="",
                        timezone="Europe/Gibraltar",
                        duration_days=duration,
                        price=price,
                        currency="GBP",
                        vat_included=None,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(url),
                        source_url=url,
                        last_verified=now,
                        freshness_status="enquire",
                    )
                )

        logger.info(
            "GibraltarMaritime adapter: %d offerings from %d pages",
            len(all_offerings),
            len(_COURSE_PAGES),
        )
        return all_offerings
