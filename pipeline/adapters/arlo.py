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

# £ is U+00A3; match both the literal and the unicode escape for safety
_PRICE_RE = re.compile(r"[££]\s*([\d,]+(?:\.\d{2})?)")
_REGISTER_HREF_RE = re.compile(r"arlo\.co.*register", re.I)


class ArloAdapter(BaseAdapter):
    def __init__(self, subdomain: str, course_path: str, course_id: str):
        self.subdomain = subdomain
        self.course_path = course_path
        self.course_id = course_id
        self.source_url = f"https://www.{subdomain}.com{course_path}"

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        try:
            resp = session.get(self.source_url, timeout=20)
            resp.raise_for_status()
            time.sleep(2)
        except Exception as e:
            logger.warning("Arlo fetch failed for %s: %s", self.source_url, e)
            return []

        try:
            return self._parse(resp.text, provider)
        except Exception as e:
            logger.warning("Arlo parse failed for %s: %s", self.source_url, e)
            return []

    def _parse(self, html: str, provider: dict) -> list[Offering]:
        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()

        # The MSA Arlo page wraps each session in a div with class "event"
        event_divs = soup.find_all("div", class_="event")

        for container in event_divs:
            start_span = container.find("span", class_="arlo-start-date")
            end_span = container.find("span", class_="arlo-end-date")
            if not start_span:
                continue

            start_date = _parse_date(start_span.get_text(strip=True))
            if not start_date:
                continue

            end_date = (
                _parse_date(end_span.get_text(strip=True)) if end_span else start_date
            )
            if not end_date:
                end_date = start_date

            price, vat_included = _extract_price(container)
            booking_url = safe_url(_extract_booking_url(container))
            availability = _extract_availability(container)

            offering_id = f"{self.course_id}-{provider['id']}-{start_date}"[:80]

            offerings.append(
                Offering(
                    id=offering_id,
                    course_id=self.course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=end_date,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP" if price is not None else None,
                    vat_included=vat_included,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=booking_url,
                    source_url=self.source_url,
                    last_verified=now,
                    freshness_status="verified",
                )
            )

        logger.info(
            "Arlo adapter extracted %d offerings from %s",
            len(offerings),
            self.source_url,
        )
        return offerings


def _parse_date(text: str) -> str | None:
    """Parse a human date string like '10 August 2026' into ISO format."""
    try:
        return dateutil_parser.parse(text).date().isoformat()
    except Exception:
        return None


def _extract_price(container) -> tuple[float | None, bool | None]:
    """Return (price_float, vat_included) from an event container."""
    amount_span = container.find("span", class_="amount")
    if not amount_span:
        # Fall back to searching the full text
        text = container.get_text(" ", strip=True)
        m = _PRICE_RE.search(text)
        if not m:
            return None, None
        price = float(m.group(1).replace(",", ""))
    else:
        m = _PRICE_RE.search(amount_span.get_text(strip=True))
        if not m:
            return None, None
        price = float(m.group(1).replace(",", ""))

    tax_span = container.find("span", class_="arlo-price-tax")
    if tax_span:
        tax_text = tax_span.get_text(strip=True).lower()
        if "incl" in tax_text and "vat" in tax_text:
            vat_included = True
        elif "excl" in tax_text and "vat" in tax_text:
            vat_included = False
        else:
            vat_included = None
    else:
        full_text = container.get_text(" ", strip=True).lower()
        if "incl" in full_text and "vat" in full_text:
            vat_included = True
        elif "excl" in full_text and "vat" in full_text:
            vat_included = False
        else:
            vat_included = None

    return price, vat_included


def _extract_booking_url(container) -> str | None:
    """Return the Arlo registration link from an event container."""
    link = container.find("a", href=_REGISTER_HREF_RE)
    if link:
        return link.get("href")
    return None


def _extract_availability(container) -> str | None:
    """Return availability text (e.g. '5 places remaining') if present."""
    places_span = container.find("span", class_="arlo-places-remaining")
    if places_span:
        return places_span.get_text(strip=True) or None
    return None
