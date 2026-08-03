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

CALENDAR_URL = "https://youandsea.com/course-calendar"

# Match date strings like "10 August 2026" or "10 Aug 2026"
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")

# Match price strings like "£550.00" or "£ 550"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")


class YouAndSeaAdapter(BaseAdapter):
    """Adapter for You and Sea Ltd (youandsea.com).

    The course calendar page is served by Squarespace and dates are rendered
    client-side via JavaScript. When fetched server-side the HTML contains no
    schedule data, so this adapter returns an empty list with a warning rather
    than fabricating data.

    If Squarespace ever begins including server-rendered event markup (e.g.
    ``<time>`` elements or ``div.eventlist-event`` blocks) this adapter will
    pick those up automatically via the parsing strategies below.
    """

    def __init__(self, course_id: str, source_url: str = CALENDAR_URL):
        self.course_id = course_id
        self.source_url = source_url

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        try:
            resp = session.get(self.source_url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("YouAndSea fetch failed for %s: %s", self.source_url, e)
            return []
        time.sleep(2)
        try:
            return self._parse(resp.text, provider)
        except Exception as e:
            logger.warning("YouAndSea parse failed for %s: %s", self.source_url, e)
            return []

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()
        seen_dates: set[str] = set()

        # Strategy 1: Squarespace event list items
        # Squarespace renders events as <article class="eventlist-event"> with
        # <time datetime="YYYY-MM-DDTHH:MM:SS"> child elements when SSR is active.
        for article in soup.find_all("article", class_=re.compile(r"eventlist", re.I)):
            time_el = article.find("time", datetime=True)
            if not time_el:
                continue
            try:
                d = dateutil_parser.parse(time_el["datetime"]).date().isoformat()
            except Exception:
                continue
            if d in seen_dates:
                continue
            seen_dates.add(d)
            link = article.find("a", href=True)
            booking = safe_url(link["href"] if link else self.source_url)
            price, vat_included, currency = _extract_price(article)
            offerings.append(Offering(
                id=f"{self.course_id}-youandsea-{d}",
                course_id=self.course_id,
                provider_id=provider["id"],
                start_date=d,
                end_date=d,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency=currency,
                vat_included=vat_included,
                delivery_format="in_person",
                availability=None,
                booking_url=booking,
                source_url=self.source_url,
                last_verified=now,
                freshness_status="verified",
            ))

        # Strategy 2: any element with a date-related class name containing a date
        if not offerings:
            date_elements = soup.find_all(
                class_=re.compile(r"date|schedule|session|event", re.I)
            )
            for el in date_elements:
                text = el.get_text(" ", strip=True)
                for match in _DATE_RE.finditer(text):
                    try:
                        d = dateutil_parser.parse(match.group(), fuzzy=False).date().isoformat()
                    except Exception:
                        continue
                    if d in seen_dates:
                        continue
                    seen_dates.add(d)
                    link = el.find("a", href=True)
                    price, vat_included, currency = _extract_price(el)
                    offerings.append(Offering(
                        id=f"{self.course_id}-youandsea-{d}",
                        course_id=self.course_id,
                        provider_id=provider["id"],
                        start_date=d,
                        end_date=d,
                        timezone="Europe/London",
                        duration_days=None,
                        price=price,
                        currency=currency,
                        vat_included=vat_included,
                        delivery_format="in_person",
                        availability=None,
                        booking_url=safe_url(link["href"] if link else self.source_url),
                        source_url=self.source_url,
                        last_verified=now,
                        freshness_status="verified",
                    ))

        if not offerings:
            logger.warning(
                "YouAndSea: no schedule data found at %s — page may be JavaScript-rendered "
                "(Squarespace). Returning empty list.",
                self.source_url,
            )

        logger.info(
            "YouAndSea adapter extracted %d offerings from %s",
            len(offerings),
            self.source_url,
        )
        return offerings


def _extract_price(container) -> tuple[float | None, bool | None, str | None]:
    """Return (price_float, vat_included, currency) from a container."""
    text = container.get_text(" ", strip=True)
    m = _PRICE_RE.search(text)
    if not m:
        return None, None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None, None
    text_lower = text.lower()
    if "incl" in text_lower and "vat" in text_lower:
        vat_included = True
    elif "excl" in text_lower and "vat" in text_lower:
        vat_included = False
    else:
        vat_included = None
    return price, vat_included, "GBP"
