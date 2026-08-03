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

COURSE_URLS = {
    "pst": "https://www.uksa.org/course/personal-survival-techniques/",
    "fpff": "https://www.uksa.org/course/fire-fighting-and-fire-prevention/",
    "efa": "https://www.uksa.org/course/elementary-first-aid/",
    # UKSA does not list PSSR as a standalone course; omitted
}

# Match date strings like "10 August 2026" or "10 Aug 2026"
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")


class UKSAAdapter(BaseAdapter):
    def __init__(self, course_id: str):
        self.course_id = course_id
        self.source_url = COURSE_URLS.get(course_id, "https://www.uksa.org/courses")

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        try:
            resp = session.get(self.source_url, timeout=20)
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

        # Strategy 1: look for elements with date-related class names
        date_elements = (
            soup.find_all(class_=re.compile(r"date|schedule|session|event", re.I))
        )

        seen_dates: set[str] = set()

        for el in date_elements:
            text = el.get_text(" ", strip=True)
            for match in _DATE_RE.finditer(text):
                try:
                    d = dateutil_parser.parse(match.group(), fuzzy=False).date().isoformat()
                    if d in seen_dates:
                        continue
                    seen_dates.add(d)
                    link = el.find("a", href=True)
                    booking = safe_url(link["href"] if link else self.source_url)
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
                        booking_url=booking,
                        source_url=self.source_url,
                        last_verified=now,
                        freshness_status="verified",
                    ))
                except Exception:
                    continue

        # Strategy 2: fallback — scan all text nodes for date patterns
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
