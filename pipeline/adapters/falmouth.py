"""Falmouth Training Solutions adapter.

Course pages live at falmouthtrainingsolutions.co.uk/courses/...
Each course page has dates as plain text in the format:
  "Mon 17 August - Fri 21 August 2026"
and a price like "£985".
We enumerate known course slugs and scrape each page.
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
USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

BASE = "https://falmouthtrainingsolutions.co.uk"

# course_id -> relative path to course page
COURSE_PAGES: dict[str, str] = {
    "pst":  "/courses/stcw-basic-training-courses/stcw-basic-safety-training-course-falmouth-training-solutions/",
    "fpff": "/courses/stcw-basic-training-courses/stcw-basic-safety-training-course-falmouth-training-solutions/",
    "efa":  "/courses/stcw-basic-training-courses/stcw-basic-safety-training-course-falmouth-training-solutions/",
    "pssr": "/courses/stcw-basic-training-courses/stcw-basic-safety-training-course-falmouth-training-solutions/",
}

# "Mon 17 August - Fri 21 August 2026"  or  "Mon 17 August 2026"
_DATE_RANGE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)"
    r"(?:\s*[-–]\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4}))?",
    re.I,
)
_PRICE_RE = re.compile(r"[£\xA3]([\d,]+(?:\.\d{2})?)")


class FalmouthAdapter(BaseAdapter):
    def __init__(self, course_id: str):
        self.course_id = course_id

    def fetch(self, provider: dict) -> list[Offering]:
        path = COURSE_PAGES.get(self.course_id)
        if not path:
            return []
        url = BASE + path
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Falmouth fetch failed %s: %s", url, e)
            return []
        time.sleep(2)
        try:
            return self._parse(resp.text, provider, url)
        except Exception as e:
            logger.warning("Falmouth parse failed %s: %s", url, e)
            return []

    def _parse(self, html: str, provider: dict, url: str) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()
        offerings: list[Offering] = []
        seen: set[str] = set()

        # Find the price once from page
        price = None
        vat_included = None
        pm = _PRICE_RE.search(soup.get_text())
        if pm:
            try:
                price = float(pm.group(1).replace(",", ""))
                vat_included = False  # shown as ex-VAT on site
            except ValueError:
                pass

        full_text = soup.get_text(" ", strip=True)
        for m in _DATE_RANGE_RE.finditer(full_text):
            start_str = m.group(1).strip()
            end_str = (m.group(2) or start_str).strip()
            # end_str might lack year — append from end_str or start_str
            if not re.search(r"\d{4}", start_str):
                year = re.search(r"\d{4}", end_str)
                if year:
                    start_str += f" {year.group()}"
            try:
                start_d = dateutil_parser.parse(start_str, fuzzy=True).date().isoformat()
                end_d = dateutil_parser.parse(end_str, fuzzy=True).date().isoformat()
            except Exception:
                continue
            if start_d in seen:
                continue
            seen.add(start_d)
            offerings.append(Offering(
                id=f"{self.course_id}-falmouth-{start_d}",
                course_id=self.course_id,
                provider_id=provider["id"],
                start_date=start_d,
                end_date=end_d,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP" if price else None,
                vat_included=vat_included,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(url),
                source_url=url,
                last_verified=now,
                freshness_status="verified",
            ))

        logger.info("Falmouth adapter: %d offerings for %s", len(offerings), self.course_id)
        return offerings
