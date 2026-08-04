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

# Match date strings like "10 August 2026" or "10 Aug 2026"
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")

# Match price strings like "£550.00" or "£ 550"
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")


class StreamMarineAdapter(BaseAdapter):
    def __init__(self, course_id: str, source_url: str):
        self.course_id = course_id
        self.source_url = source_url

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        try:
            resp = session.get(self.source_url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("StreamMarine fetch failed for %s: %s", self.source_url, e)
            return []
        time.sleep(2)
        try:
            return self._parse(resp.text, provider)
        except Exception as e:
            logger.warning("StreamMarine parse failed for %s: %s", self.source_url, e)
            return []

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()
        seen_dates: set[str] = set()

        # Strategy 1: Stream Marine's bespoke smt-event structure.
        # Each session is a <div class="smt-event"> containing:
        #   <div class="smt-event-date">DD Mon YYYY</div>
        #   <div class="smt-event-register"><a href="https://...arlo.co/...">Register</a>
        #     <span class="arlo-places-remaining">N places remaining</span>
        #   </div>
        smt_events = soup.find_all("div", class_="smt-event")
        for event_el in smt_events:
            date_el = event_el.find(class_="smt-event-date")
            if not date_el:
                continue
            m = _DATE_RE.search(date_el.get_text(strip=True))
            if not m:
                continue
            try:
                d = dateutil_parser.parse(m.group(), fuzzy=False).date().isoformat()
            except Exception:
                continue
            if d in seen_dates:
                continue
            seen_dates.add(d)
            link = event_el.find("a", href=True)
            # Availability from "N places remaining" span
            avail_el = event_el.find(class_="arlo-places-remaining")
            availability = avail_el.get_text(strip=True) if avail_el else None
            price, vat_included, currency = _extract_price(event_el)
            offerings.append(Offering(
                id=f"{self.course_id}-stream-{d}",
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
                availability=availability,
                booking_url=safe_url(link["href"] if link else self.source_url),
                source_url=self.source_url,
                last_verified=now,
                freshness_status="verified",
            ))

        # Strategy 2: table rows — fallback for Arlo event pages that render <tr> with date cells
        if not offerings:
            for row in soup.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                for cell in cells:
                    text = cell.get_text(strip=True)
                    m = _DATE_RE.search(text)
                    if not m:
                        continue
                    try:
                        d = dateutil_parser.parse(m.group(), fuzzy=False).date().isoformat()
                    except Exception:
                        continue
                    if d in seen_dates:
                        continue
                    seen_dates.add(d)
                    link = row.find("a", href=True)
                    price, vat_included, currency = _extract_price(row)
                    offerings.append(Offering(
                        id=f"{self.course_id}-stream-{d}",
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
                    break  # one date per row

        # Strategy 3: elements with date-related class names (last resort)
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
                        id=f"{self.course_id}-stream-{d}",
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

        logger.info(
            "StreamMarine adapter extracted %d offerings from %s",
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
