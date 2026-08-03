"""STCW Training UK Ltd adapter.

Scrapes the JS-rendered events calendar at stcw-training-uk.com/events/ using
Playwright to extract upcoming course dates, names and prices.

Course ID mapping
-----------------
PST / Personal Survival              -> pst
EFA / Elementary First Aid / First Aid -> efa
FPFF / Fire Prevention               -> fpff
PSSR / Personal Safety               -> pssr
Basic Safety / STCW Basic            -> pst
PSCRB                                -> pscrb
AFF / Advanced Fire                  -> aff
"""
import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

PROVIDER_ID = "stcw-training-uk-ltd"
SOURCE_URL = "https://stcw-training-uk.com/events/"

# -----------------------------------------------------------------------
# Course ID inference
# -----------------------------------------------------------------------
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"proficiency.in.survival.craft|pscrb", re.I), "pscrb"),
    (re.compile(r"advanced.fire|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]|first.aid", re.I), "efa"),
    (re.compile(r"fire.prevention|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.survival|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"personal.safety|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"basic.safety|stcw.basic", re.I), "pst"),
]

# Price: £123 or £1,234.56
_PRICE_RE = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")

# Date patterns — ISO (2026-08-15), UK long (15 August 2026 / 15 Aug 2026),
# UK short (15/08/2026), US-ish (August 15, 2026)
_DATE_PATTERNS = [
    # ISO: 2026-08-15
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    # DD Month YYYY or DD Mon YYYY
    re.compile(
        r"\b(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(\d{4})\b",
        re.I,
    ),
    # Month DD, YYYY
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+(\d{1,2}),?\s+(\d{4})\b",
        re.I,
    ),
    # DD/MM/YYYY
    re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b"),
]

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(text: str) -> str | None:
    """Try to extract and normalise a date string. Returns ISO date or None."""
    text = text.strip()

    # ISO
    m = _DATE_PATTERNS[0].search(text)
    if m:
        try:
            datetime.strptime(m.group(1), "%Y-%m-%d")
            return m.group(1)
        except ValueError:
            pass

    # DD Month YYYY
    m = _DATE_PATTERNS[1].search(text)
    if m:
        day = int(m.group(1))
        month = _MONTH_NAMES.get(m.group(2).lower())
        year = int(m.group(3))
        if month:
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                pass

    # Month DD, YYYY
    m = _DATE_PATTERNS[2].search(text)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        day = int(m.group(2))
        year = int(m.group(3))
        if month:
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                pass

    # DD/MM/YYYY
    m = _DATE_PATTERNS[3].search(text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date().isoformat()
        except ValueError:
            pass

    return None


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _extract_price(text: str) -> tuple[float | None, bool | None]:
    m = _PRICE_RE.search(text)
    if not m:
        return None, None
    try:
        price = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, None
    lower = text.lower()
    if "incl" in lower and "vat" in lower:
        vat_included = True
    elif "excl" in lower and "vat" in lower:
        vat_included = False
    else:
        vat_included = None
    return price, vat_included


# -----------------------------------------------------------------------
# Adapter
# -----------------------------------------------------------------------

class StcwTrainingUkAdapter(PlaywrightAdapter):
    """Adapter for STCW Training UK Ltd — JS-rendered events calendar."""

    def __init__(self) -> None:
        pass

    def fetch(self, provider: dict) -> list[Offering]:
        try:
            return self._fetch(provider)
        except Exception as e:
            logger.warning("StcwTrainingUk: unexpected error: %s", e)
            return []

    def _fetch(self, provider: dict) -> list[Offering]:
        # Candidate selectors to wait for on the events page.
        # Try a broad article/event selector first; fall back to networkidle.
        html = self.fetch_rendered(
            SOURCE_URL,
            wait_selector=".tribe-events-calendar, .tribe_events_cat, "
                          ".tribe-event-url, article.type-tribe_events, "
                          ".tribe-events-loop, .tribe-common-l-container",
            timeout=30000,
        )

        if not html:
            # Playwright not installed or fetch failed
            return []

        try:
            offerings = _parse_events_html(html, provider)
        except Exception as e:
            logger.warning("StcwTrainingUk: parse error: %s", e)
            return []

        logger.info("StcwTrainingUk adapter: %d offerings extracted", len(offerings))
        return offerings


# -----------------------------------------------------------------------
# HTML parsing
# -----------------------------------------------------------------------

def _parse_events_html(html: str, provider: dict) -> list[Offering]:
    """Parse offerings from the rendered events page HTML."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    # Strategy 1 — The Events Calendar plugin (The Tribe Events Calendar)
    # Event items are typically <article class="type-tribe_events ..."> or
    # inside <div class="tribe-events-loop">
    event_articles = soup.find_all(
        "article",
        class_=re.compile(r"type-tribe_events|tribe-event", re.I),
    )

    if event_articles:
        for article in event_articles:
            _extract_from_element(article, provider, now, seen, offerings)

    # Strategy 2 — generic list items / divs that carry date metadata
    if not offerings:
        # Look for elements with datetime attributes (common in modern event plugins)
        for el in soup.find_all(attrs={"datetime": True}):
            parent = el.find_parent(
                ["article", "li", "div"],
                class_=re.compile(r"event|course|schedule|booking", re.I),
            ) or el.parent
            if parent:
                _extract_from_element(parent, provider, now, seen, offerings)

    # Strategy 3 — walk every list item / row and look for date + course name
    if not offerings:
        candidates = soup.find_all(
            ["li", "tr", "div"],
            class_=re.compile(r"event|course|schedule|booking|listing|item", re.I),
        )
        for el in candidates:
            _extract_from_element(el, provider, now, seen, offerings)

    # Strategy 4 — full-page text scan as last resort
    if not offerings:
        _full_page_scan(soup, provider, now, seen, offerings)

    return offerings


def _extract_from_element(
    el,
    provider: dict,
    now: str,
    seen: set[str],
    offerings: list[Offering],
) -> None:
    """Try to build an Offering from a BeautifulSoup element."""
    text = el.get_text(" ", strip=True)

    # 1. Find start date
    start_date: str | None = None

    # Check for machine-readable datetime attribute first
    for tag in el.find_all(attrs={"datetime": True}):
        val = tag["datetime"]
        parsed = _parse_date(val)
        if parsed:
            start_date = parsed
            break

    if not start_date:
        start_date = _parse_date(text)

    if not start_date:
        return

    # 2. Determine course ID
    # Prefer heading text, then full element text
    heading = el.find(re.compile(r"^h[1-6]$"))
    heading_text = heading.get_text(" ", strip=True) if heading else ""
    course_id = _course_id_from_text(heading_text) or _course_id_from_text(text)

    if not course_id:
        return

    # 3. Deduplicate on course_id + start_date
    key = f"{course_id}:{start_date}"
    if key in seen:
        return
    seen.add(key)

    # 4. Price
    price, vat_included = _extract_price(text)

    # 5. Booking URL — look for an <a> inside the element
    booking_url: str | None = None
    a_tag = el.find("a", href=True)
    if a_tag:
        href = a_tag["href"]
        if href.startswith("http"):
            booking_url = href
        elif href.startswith("/"):
            booking_url = "https://stcw-training-uk.com" + href

    offering_id = f"{course_id}-stcw-training-uk-{start_date}"

    offerings.append(
        Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider["id"],
            start_date=start_date,
            end_date=start_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=vat_included,
            delivery_format="in_person",
            availability=None,
            booking_url=safe_url(booking_url or SOURCE_URL),
            source_url=SOURCE_URL,
            last_verified=now,
            freshness_status="verified",
        )
    )


def _full_page_scan(
    soup,
    provider: dict,
    now: str,
    seen: set[str],
    offerings: list[Offering],
) -> None:
    """Last-resort: scan full page text for date + course keyword pairs."""
    full_text = soup.get_text(" ", strip=True)

    # Split into lines and look for lines that contain both a date and a course keyword
    lines = [ln.strip() for ln in re.split(r"[\n\r]+", full_text) if ln.strip()]

    for i, line in enumerate(lines):
        start_date = _parse_date(line)
        if not start_date:
            continue

        # Check the surrounding context (current line ± 3 lines) for a course name
        ctx_lines = lines[max(0, i - 3): i + 4]
        ctx = " ".join(ctx_lines)
        course_id = _course_id_from_text(ctx)
        if not course_id:
            continue

        key = f"{course_id}:{start_date}"
        if key in seen:
            continue
        seen.add(key)

        price, vat_included = _extract_price(ctx)
        offering_id = f"{course_id}-stcw-training-uk-{start_date}"

        offerings.append(
            Offering(
                id=offering_id,
                course_id=course_id,
                provider_id=provider["id"],
                start_date=start_date,
                end_date=start_date,
                timezone="Europe/London",
                duration_days=None,
                price=price,
                currency="GBP" if price is not None else None,
                vat_included=vat_included,
                delivery_format="in_person",
                availability=None,
                booking_url=safe_url(SOURCE_URL),
                source_url=SOURCE_URL,
                last_verified=now,
                freshness_status="verified",
            )
        )
