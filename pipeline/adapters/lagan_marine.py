"""Lagan Marine Training & Recruitment adapter.

Lagan Marine (Belfast, Northern Ireland) operates a WordPress brochure site
with no public course dates, pricing, or booking system.  Every course page
only describes the syllabus and asks enquirers to phone or email directly.

This adapter crawls all known course pages to confirm which STCW courses the
provider actively offers, then returns an empty offerings list because there is
no schedule data to harvest.  The freshness_status on any future offering would
be "stale" until a date source is identified.

Provider ID : lagan-marine-training-recruitment
Website     : https://www.laganmarine.co.uk
Contact     : 028 9066 1500 / contact@laganmarine.co.uk
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

BASE_URL = "https://www.laganmarine.co.uk"
TRAINING_URL = f"{BASE_URL}/training/"

# All known course page URLs (from sitemap + training page links, Aug 2026).
# Maintained as a static list because the site has no sitemap with lastmod
# timestamps and the page count is small / stable.
_COURSE_URLS: list[str] = [
    f"{BASE_URL}/training/personal-survival-techniques/",
    f"{BASE_URL}/personal-survival-updated/",
    f"{BASE_URL}/basic-fire-prevention-fire-fighting-fpff/",
    f"{BASE_URL}/fire-prevention-fire-fighting-updated/",
    f"{BASE_URL}/training/personal-safety-and-social-responsibilities/",
    f"{BASE_URL}/first-aid/",
    f"{BASE_URL}/crisis-management/",
    f"{BASE_URL}/security-awareness/",
    f"{BASE_URL}/security-duties/",
]

# Maps text/URL keywords to normalised STCW course IDs.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"crisis.management|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"security.awareness|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


class LaganMarineAdapter(BaseAdapter):
    """Adapter for Lagan Marine Training & Recruitment, Belfast.

    NOTE: This provider does not publish course dates or a booking system
    online.  The adapter crawls the site to verify it is still active and
    which STCW courses are advertised, but always returns an empty list
    because no date/price/availability data is available to scrape.

    To enable real offerings, Lagan Marine would need to either:
      - Publish a course schedule page, or
      - Integrate an online booking system (e.g. Arlo, FareHarbor).
    """

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-GB,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        confirmed_courses: list[str] = []

        for url in _COURSE_URLS:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("LaganMarine: fetch failed %s: %s", url, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                soup = BeautifulSoup(resp.text, "lxml")
                title_tag = soup.find("h1") or soup.find("title")
                title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
                course_id = (
                    _course_id_from_text(title_text)
                    or _course_id_from_text(url)
                )
                if course_id and course_id not in confirmed_courses:
                    confirmed_courses.append(course_id)
                    logger.debug(
                        "LaganMarine: confirmed course %s at %s", course_id, url
                    )
            except Exception as e:
                logger.warning("LaganMarine: parse failed %s: %s", url, e)

        logger.info(
            "LaganMarine: site is live, confirmed STCW courses: %s. "
            "No date/booking data available — returning 0 offerings.",
            confirmed_courses,
        )

        # No schedule data is published on this site.
        return []
