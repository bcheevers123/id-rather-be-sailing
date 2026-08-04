"""RelyOn Nutec adapter.

Scrapes https://shop.relyon.com/ for STCW/MCA maritime course dates at UK
locations.  Uses two strategies:

1. Discover STCW course URLs from the sitemap (no JS required).
2. For each course page:
   a. Render with Playwright and extract the JSON-LD ``hasCourseInstance``
      array (first page, up to 10 rows).
   b. If ``hdn_total_records > page_size``, fetch remaining pages via the
      ``/Course/PagedCourseInstancesForDetails`` AJAX endpoint (JSON POST)
      and parse the returned HTML fragment with BeautifulSoup.

Location → provider_id mapping:
    Aberdeen  → relyon-nutec-aberdeen
    Glasgow   → relyon-glasgow
    Liverpool → relyon-liverpool
    Teesside  → relyon-nutec-teesside

Unknown locations fall back to ``relyon-nutec-aberdeen``.
"""
import json
import logging
import math
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import USER_AGENT, PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

BASE_URL = "https://shop.relyon.com"
SITEMAP_URL = BASE_URL + "/sitemap.xml"
AJAX_URL = BASE_URL + "/Course/PagedCourseInstancesForDetails"

# Minimum polite delay between requests (seconds)
_REQUEST_DELAY = 2.0

# ------------------------------------------------------------------
# Location → provider_id mapping
# ------------------------------------------------------------------
_LOCATION_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"aberdeen", re.I), "relyon-nutec-aberdeen"),
    (re.compile(r"glasgow", re.I), "relyon-glasgow"),
    (re.compile(r"liverpool", re.I), "relyon-liverpool"),
    (re.compile(r"teesside|tees|middlesbrough", re.I), "relyon-nutec-teesside"),
]

_FALLBACK_PROVIDER_ID = "relyon-nutec-aberdeen"

# ------------------------------------------------------------------
# Course keyword → course_id mapping (checked in order)
# ------------------------------------------------------------------
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.techniques|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"fire.prevention.and.fire.fighting|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"personal.safety.and.social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]", re.I), "pscrb"),
    (re.compile(r"advanced.fire.?fighting|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
    (re.compile(r"maritime.basic.safety", re.I), "pst"),  # BST bundle → pst
]

# ------------------------------------------------------------------
# Regex for STCW URLs in sitemap
# ------------------------------------------------------------------
_SITEMAP_STCW_RE = re.compile(
    r"<loc>(https://shop\.relyon\.com/Course/CourseDetails/\d+/2/Stcw[^<]+)</loc>"
)

# ------------------------------------------------------------------
# Regex for price in row text: "GBP 135.00" or "£135.00"
# ------------------------------------------------------------------
_PRICE_RE = re.compile(r"(?:GBP|£)\s*([\d,]+(?:\.\d{2})?)")


def _provider_id_from_location(location: str) -> str:
    for pattern, pid in _LOCATION_MAP:
        if pattern.search(location):
            return pid
    return _FALLBACK_PROVIDER_ID


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _location_slug(location: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-") or "unknown"


def _decamel(text: str) -> str:
    """Split CamelCase slug into space-separated words for keyword matching."""
    # Insert space before uppercase letters that follow lowercase letters
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Also handle digits followed by letters
    s = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", s)
    return s


class RelyOnAdapter(PlaywrightAdapter):
    """Adapter for RelyOn Nutec's booking platform (shop.relyon.com)."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html, */*",
        })

    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch STCW offerings from shop.relyon.com.

        Called once with any relyonnutec provider.  Returns offerings for all
        UK locations (provider_id determined per-row from the location field).
        """
        try:
            return self._fetch_all()
        except Exception as e:
            logger.warning("RelyOn adapter unexpected error: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_all(self) -> list[Offering]:
        now = datetime.now(timezone.utc).isoformat()
        course_urls = self._discover_course_urls()
        if not course_urls:
            logger.warning("RelyOn: no STCW course URLs found in sitemap")
            return []

        all_offerings: list[Offering] = []
        seen_ids: set[str] = set()

        for url in course_urls:
            # Slug is CamelCase — convert to words for keyword matching
            slug = url.rsplit("/", 1)[-1]
            course_id = _course_id_from_text(_decamel(slug))
            if not course_id:
                logger.debug("RelyOn: skipping (no course_id) %s", url)
                continue
            try:
                offerings = self._fetch_course_offerings(url, course_id, now)
                for o in offerings:
                    if o.id not in seen_ids:
                        seen_ids.add(o.id)
                        all_offerings.append(o)
            except Exception as e:
                logger.warning("RelyOn: error processing %s: %s", url, e)
            time.sleep(_REQUEST_DELAY)

        logger.info("RelyOn adapter: %d unique offerings total", len(all_offerings))
        return all_offerings

    def _discover_course_urls(self) -> list[str]:
        """Return STCW course URLs from the sitemap (no JS required)."""
        try:
            resp = self._session.get(SITEMAP_URL, timeout=20)
            resp.raise_for_status()
            urls = _SITEMAP_STCW_RE.findall(resp.text)
            logger.info("RelyOn: found %d STCW URLs in sitemap", len(urls))
            return urls
        except Exception as e:
            logger.warning("RelyOn: sitemap fetch failed: %s", e)
            return []

    def _fetch_course_offerings(
        self, url: str, course_id: str, now: str
    ) -> list[Offering]:
        """Render the course detail page, extract JSON-LD + paginate via AJAX."""
        # Page 1: render with Playwright to get JSON-LD and pagination metadata
        html = self.fetch_rendered(url, timeout=30000)
        if not html:
            logger.warning("RelyOn: could not render %s", url)
            return []

        soup = BeautifulSoup(html, "lxml")

        # Extract course type ID and country ID for AJAX pagination
        course_type_id_inp = soup.find("input", id="course-type-id")
        country_id_inp = soup.find("input", id="country-id")
        total_inp = soup.find("input", id="hdn_total_records")
        page_size_inp = soup.find("input", id="hdn_page_size")

        course_type_id = int(course_type_id_inp["value"]) if course_type_id_inp else None
        country_id = int(country_id_inp["value"]) if country_id_inp else 2
        total_records = int(total_inp["value"]) if total_inp else 0
        page_size = int(page_size_inp["value"]) if page_size_inp else 10

        offerings: list[Offering] = []

        # Strategy 1: JSON-LD (reliable, structured, first page only)
        ld_offerings = self._parse_jsonld(soup, course_id, url, now)
        offerings.extend(ld_offerings)

        # Strategy 2: fallback to tr_course_instance rows if JSON-LD empty
        if not ld_offerings:
            offerings.extend(
                self._parse_instance_rows(soup, course_id, url, now)
            )

        # Paginate if there are more records
        if course_type_id and total_records > page_size:
            extra_pages = math.ceil(total_records / page_size) - 1
            for page in range(2, extra_pages + 2):
                time.sleep(_REQUEST_DELAY)
                frag_offerings = self._fetch_ajax_page(
                    course_type_id, country_id, page, page_size,
                    course_id, url, now
                )
                offerings.extend(frag_offerings)

        return offerings

    def _parse_jsonld(
        self, soup: BeautifulSoup, course_id: str, page_url: str, now: str
    ) -> list[Offering]:
        """Extract offerings from JSON-LD ``hasCourseInstance`` array."""
        offerings: list[Offering] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.get_text())
            except (json.JSONDecodeError, ValueError):
                continue

            graph = data.get("@graph", [data]) if isinstance(data, dict) else []
            for node in graph:
                if node.get("@type") != "Course":
                    continue
                for inst in node.get("hasCourseInstance", []):
                    o = self._jsonld_instance_to_offering(
                        inst, course_id, page_url, now
                    )
                    if o:
                        offerings.append(o)
        return offerings

    def _jsonld_instance_to_offering(
        self, inst: dict, course_id: str, page_url: str, now: str
    ) -> "Offering | None":
        start_date = inst.get("startDate")
        end_date = inst.get("endDate") or start_date
        if not start_date:
            return None

        location_obj = inst.get("location", {})
        location = location_obj.get("name", "") if isinstance(location_obj, dict) else ""
        provider_id = _provider_id_from_location(location) if location else _FALLBACK_PROVIDER_ID

        offers = inst.get("offers", {})
        price: float | None = None
        currency: str | None = None
        if isinstance(offers, dict):
            try:
                price = float(offers["price"])
            except (KeyError, ValueError, TypeError):
                pass
            currency = offers.get("priceCurrency") or ("GBP" if price is not None else None)

        loc_slug = _location_slug(location) if location else "uk"
        offering_id = f"{course_id}-relyon-{loc_slug}-{start_date}"

        return Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency=currency,
            vat_included=False,  # site states "Ex. VAT"
            delivery_format="in_person",
            availability=None,
            booking_url=safe_url(page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        )

    def _parse_instance_rows(
        self,
        soup: BeautifulSoup,
        course_id: str,
        page_url: str,
        now: str,
    ) -> list[Offering]:
        """Fallback: parse tr.tr_course_instance rows directly from HTML."""
        offerings: list[Offering] = []
        for row in soup.find_all("tr", class_="tr_course_instance"):
            o = self._row_to_offering(row, course_id, page_url, now)
            if o:
                offerings.append(o)
        return offerings

    def _fetch_ajax_page(
        self,
        course_type_id: int,
        country_id: int,
        page: int,
        page_size: int,
        course_id: str,
        page_url: str,
        now: str,
    ) -> list[Offering]:
        """Fetch a paginated HTML fragment via the AJAX endpoint."""
        try:
            resp = self._session.post(
                AJAX_URL,
                json={
                    "courseTypeId": course_type_id,
                    "countryId": country_id,
                    "page": page,
                    "pageSize": page_size,
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": page_url,
                },
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning("RelyOn AJAX page %d failed for %s: %s", page, page_url, e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse_instance_rows(soup, course_id, page_url, now)

    def _row_to_offering(
        self, row, course_id: str, page_url: str, now: str
    ) -> "Offering | None":
        """Build an Offering from a tr.tr_course_instance row."""
        text = row.get_text(" ", strip=True)

        # Dates: two dates appear in the text; first is start, second is end
        # Pattern: "Date from 06 Aug 2026 06 Aug 2026"
        date_pattern = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b")
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        dates = []
        for m in date_pattern.finditer(text):
            month = month_map.get(m.group(2).lower()[:3])
            if month:
                dates.append(f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}")

        if not dates:
            return None

        start_date = dates[0]
        end_date = dates[1] if len(dates) > 1 else start_date

        # Location
        loc_m = re.search(
            r"Location\s+([A-Z][a-zA-Z\s\-]{1,30}?)(?:\s+Language|\s+Price|\s*$)",
            text,
        )
        location = loc_m.group(1).strip() if loc_m else ""
        provider_id = _provider_id_from_location(location) if location else _FALLBACK_PROVIDER_ID

        # Price
        price = _parse_price(text)

        loc_slug = _location_slug(location) if location else "uk"
        offering_id = f"{course_id}-relyon-{loc_slug}-{start_date}"

        # Availability
        availability: str | None = None
        if re.search(r"fully.booked|sold.out|no.places|wait.list|call.for", text, re.I):
            availability = "Fully booked"

        return Offering(
            id=offering_id,
            course_id=course_id,
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency="GBP" if price is not None else None,
            vat_included=False,
            delivery_format="in_person",
            availability=availability,
            booking_url=safe_url(page_url),
            source_url=page_url,
            last_verified=now,
            freshness_status="verified",
        )
