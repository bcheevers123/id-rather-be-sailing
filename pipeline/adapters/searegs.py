"""SeaRegs Training Ltd adapter.

SeaRegs uses the Arlo hosted training platform at ipowerboat.arlo.co.
The /w/upcoming/ page is server-side rendered and paginated (page-2, page-3 …).
Each course card contains: course title link, date text, location, price,
availability status.

Arlo card HTML (server-rendered):
  <div class="event-card-container ...">
    <div class="card-front ...">
      <div class="event-content ...">
        <a class="event-name" href="/w/events/NNN-...">Course Title</a>
        <span class="event-date-time">Wed 5 Aug 2026</span>
        <span class="event-location">Plymouth, Devon</span>
        <span class="event-price">£170.00 incl. VAT</span>
        <span class="event-availability">Available</span>
      </div>
    </div>
  </div>

Because the exact inner-class names can vary by Arlo release, we also fall
back to text-based heuristics on the card body.
"""
import logging
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

ARLO_BASE = "https://ipowerboat.arlo.co"
UPCOMING_URL = f"{ARLO_BASE}/w/upcoming/"

# Maps course-name fragments to normalised course IDs (first match wins).
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prevention|fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]|security.awareness|proficiency.in.security", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|survival.craft.*rescue|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]\bmc\b[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# Price: £170.00 or £ 170.00
_PRICE_RE = re.compile(r"[££]\s*([\d,]+(?:\.\d{2})?)")

# Date patterns:
#   "Wed 5 Aug 2026" / "5 Aug 2026" / "5 - 7 Aug 2026" / "5–7 Aug 2026"
_DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
)
_SINGLE_DATE_RE = re.compile(
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
    re.I,
)


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, cid in _COURSE_ID_MAP:
        if pattern.search(padded):
            return cid
    return None


def _parse_date_text(text: str) -> tuple[str | None, str | None]:
    """Return (start_iso, end_iso) from date text, or (None, None)."""
    # Try range first: "5 - 7 Aug 2026"
    m = _DATE_RANGE_RE.search(text)
    if m:
        day1, day2, month, year = m.group(1), m.group(2), m.group(3), m.group(4)
        try:
            start = dateutil_parser.parse(f"{day1} {month} {year}").date().isoformat()
            end = dateutil_parser.parse(f"{day2} {month} {year}").date().isoformat()
            return start, end
        except Exception:
            pass

    # Single date: "Wed 5 Aug 2026"
    m = _SINGLE_DATE_RE.search(text)
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        try:
            iso = dateutil_parser.parse(f"{day} {month} {year}").date().isoformat()
            return iso, iso
        except Exception:
            pass

    return None, None


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    price = float(m.group(1).replace(",", ""))
    lower = text.lower()
    if "incl" in lower and "vat" in lower:
        vat = True
    elif "excl" in lower and "vat" in lower:
        vat = False
    else:
        vat = None
    return price, vat


def _extract_availability(text: str) -> str | None:
    lower = text.lower()
    if "sold out" in lower:
        return "Sold out"
    if "limited" in lower:
        m = re.search(r"(\d+)\s+place", lower)
        if m:
            return f"{m.group(1)} place{'s' if int(m.group(1)) != 1 else ''} remaining"
        return "Limited places"
    if "available" in lower or "open" in lower:
        return "Available"
    return None


def _parse_card(card: Tag, now: str, provider: dict) -> Offering | None:
    """Parse a single Arlo event card (server-rendered HTML)."""
    card_text = card.get_text(" ", strip=True)

    # --- Course name ---
    # Try heading / named link first
    name_tag = (
        card.find(class_=re.compile(r"event.name|course.name|event.title", re.I))
        or card.find("h2")
        or card.find("h3")
        or card.find("h4")
        or card.find("a", href=re.compile(r"/w/events?/", re.I))
    )
    course_name = name_tag.get_text(" ", strip=True) if name_tag else card_text[:80]

    course_id = _course_id_from_text(course_name) or _course_id_from_text(card_text)
    if not course_id:
        return None  # not an STCW course we track

    # --- Dates ---
    date_tag = card.find(class_=re.compile(r"event.date|date.time|session.date", re.I))
    date_text = date_tag.get_text(" ", strip=True) if date_tag else card_text
    start_date, end_date = _parse_date_text(date_text)
    if not start_date:
        # Last-resort: scan the whole card text
        start_date, end_date = _parse_date_text(card_text)
    if not start_date:
        logger.debug("SeaRegs: could not parse date from: %s", card_text[:120])
        return None

    # --- Price ---
    price, vat_included = _extract_price(card_text)

    # --- Availability ---
    avail_tag = card.find(class_=re.compile(r"availab|places|status", re.I))
    avail_text = avail_tag.get_text(" ", strip=True) if avail_tag else card_text
    availability = _extract_availability(avail_text)

    # --- Booking URL ---
    link_tag = (
        card.find("a", href=re.compile(r"/w/events?/\d+", re.I))
        or card.find("a", href=re.compile(r"register|book", re.I))
    )
    booking_url = safe_url(
        (ARLO_BASE + link_tag["href"])
        if link_tag and link_tag.get("href", "").startswith("/")
        else (link_tag["href"] if link_tag else None)
    )

    offering_id = f"{course_id}-searegs-training-ltd-{start_date}"[:80]

    return Offering(
        id=offering_id,
        course_id=course_id,
        provider_id=provider["id"],
        start_date=start_date,
        end_date=end_date or start_date,
        timezone="Europe/London",
        duration_days=None,
        price=price,
        currency="GBP" if price is not None else None,
        vat_included=vat_included,
        delivery_format="in_person",
        availability=availability,
        booking_url=booking_url,
        source_url=UPCOMING_URL,
        last_verified=now,
        freshness_status="verified",
    )


class SearegsAdapter(BaseAdapter):
    """Scrape STCW course dates from SeaRegs Training (ipowerboat.arlo.co)."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        offerings: list[Offering] = []
        seen_ids: set[str] = set()
        now = datetime.now(timezone.utc).isoformat()

        page = 1
        while True:
            url = UPCOMING_URL if page == 1 else f"{UPCOMING_URL}page-{page}/"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("SeaRegs fetch failed (page %d) %s: %s", page, url, e)
                break
            time.sleep(2)

            try:
                page_offerings, has_more = self._parse_page(
                    resp.text, now, provider, seen_ids
                )
            except Exception as e:
                logger.warning("SeaRegs parse failed (page %d): %s", page, e)
                break

            offerings.extend(page_offerings)

            if not has_more:
                break
            page += 1
            if page > 20:  # safety cap
                logger.warning("SeaRegs: hit page cap (20), stopping")
                break

        logger.info(
            "SeaRegs adapter: %d STCW offerings across %d page(s)", len(offerings), page
        )
        return offerings

    def _parse_page(
        self,
        html: str,
        now: str,
        provider: dict,
        seen_ids: set[str],
    ) -> tuple[list[Offering], bool]:
        """Parse one Arlo upcoming page. Returns (offerings, has_next_page)."""
        soup = BeautifulSoup(html, "lxml")

        # Arlo renders cards with class "event-card-container" (confirmed via JS).
        # Fall back to broader selectors if that misses anything.
        cards: list[Tag] = (
            soup.find_all("div", class_=re.compile(r"event.card", re.I))
            or soup.find_all("div", class_=re.compile(r"card.front", re.I))
            or soup.find_all("div", class_=re.compile(r"event.content", re.I))
            # Last resort: any block that mentions a £ price and a year
            or [
                tag
                for tag in soup.find_all("div")
                if re.search(r"[££]", tag.get_text())
                and re.search(r"\b20\d\d\b", tag.get_text())
                and len(tag.get_text()) < 600
            ]
        )

        page_offerings: list[Offering] = []
        for card in cards:
            try:
                offering = _parse_card(card, now, provider)
            except Exception as e:
                logger.debug("SeaRegs card parse error: %s", e)
                continue
            if offering is None:
                continue
            if offering.id in seen_ids:
                continue
            seen_ids.add(offering.id)
            page_offerings.append(offering)

        # Check for a "next page" / "show more" link
        has_more = bool(
            soup.find("a", href=re.compile(r"/w/upcoming/page-\d+", re.I))
            or soup.find(string=re.compile(r"show more|next page", re.I))
        )

        return page_offerings, has_more
