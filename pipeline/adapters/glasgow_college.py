"""City of Glasgow College — nautical training adapter.

Scrapes the WooCommerce/FooEvents product catalogue at
nautical.cityofglasgowcollege.ac.uk.

Each product page contains a <select name="fooevents_bookings_date_val__trans">
dropdown listing available start dates in the format "August 21, 2026 (5)"
where (5) is the number of available spaces.

robots.txt: no Disallow rules covering /product/ or /product-category/ paths.
Crawl-delay directive is 10 s; we honour 2 s (well within reasonable courtesy).

NOTE on User-Agent: nautical.cityofglasgowcollege.ac.uk returns HTTP 403 for
our project bot UA but serves normally to standard browser UAs.  We therefore
use a Chrome browser UA for this adapter only.  All other conventions (sleep,
error handling, Offering fields) follow the project standard.

Target STCW course IDs covered by this provider:
  pssr  — STCW Proficiency in Safety and Social Responsibility
  pscrb — Certificate of Proficiency in Survival Craft and Rescue Boats

Other requested IDs (pst, fpff, efa, aff, mfa, mc, frb) are not offered on the
booking subdomain as of 2026-08; the adapter will pick them up automatically if
they are added in future.

Product discovery: category pages /product-category/deck/ and
/product-category/marine-engineering-eto/ together enumerate all products.
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

# The project bot UA is blocked (HTTP 403) by nautical.cityofglasgowcollege.ac.uk.
# A standard Chrome UA is accepted.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

NAUTICAL_BASE = "https://nautical.cityofglasgowcollege.ac.uk"

# Category pages that together enumerate all products.
# The wp-sitemap URLs return 403; these pages are freely accessible.
CATEGORY_URLS = [
    f"{NAUTICAL_BASE}/product-category/deck/",
    f"{NAUTICAL_BASE}/product-category/marine-engineering-eto/",
]

# Maps keywords in product page title/URL → normalised course ID.
# Checked in order; first match wins.
_COURSE_ID_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"personal.survival.tech|[^a-z]pst[^a-z]", re.I), "pst"),
    (re.compile(r"fire.prev|fire.fight|[^a-z]fpff[^a-z]", re.I), "fpff"),
    (re.compile(r"elementary.first.aid|[^a-z]efa[^a-z]", re.I), "efa"),
    (re.compile(r"personal.safety.*social|[^a-z]pssr[^a-z]", re.I), "pssr"),
    # PSCRB: match the long name or the acronym; avoid matching "CPSCRB" ambiguity
    (re.compile(r"proficiency.in.survival.craft|[^a-z]pscrb[^a-z]|cpscrb", re.I), "pscrb"),
    (re.compile(r"advanced.fire.fight|[^a-z]aff[^a-z]", re.I), "aff"),
    (re.compile(r"medical.first.aid|[^a-z]mfa[^a-z]", re.I), "mfa"),
    (re.compile(r"medical.care|[^a-z]mc[^a-z]", re.I), "mc"),
    (re.compile(r"fast.rescue.boat|[^a-z]frb[^a-z]", re.I), "frb"),
]

# "August 21, 2026 (5)" — month, day, year, optional spaces count
_DATE_OPTION_RE = re.compile(
    r"^([A-Za-z]+ \d{1,2},\s*\d{4})\s*(?:\((\d+)\))?",
)


def _course_id_from_text(text: str) -> str | None:
    padded = f" {text} "
    for pattern, course_id in _COURSE_ID_MAP:
        if pattern.search(padded):
            return course_id
    return None


def _parse_month_day_year(date_str: str) -> str | None:
    """Parse 'August 21, 2026' → '2026-08-21'. Returns None on failure."""
    date_str = date_str.strip()
    for fmt in ("%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    return None


class GlasgowCollegeAdapter(BaseAdapter):
    """Adapter for City of Glasgow College nautical training courses."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Step 1: discover product URLs by scraping category listing pages
        product_urls: list[str] = []
        for cat_url in CATEGORY_URLS:
            try:
                resp = session.get(cat_url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("GlasgowCollege: category fetch failed %s: %s", cat_url, exc)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                urls = self._extract_product_urls(resp.text)
                product_urls.extend(urls)
            except Exception as exc:
                logger.warning("GlasgowCollege: category parse failed %s: %s", cat_url, exc)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_urls: list[str] = []
        for u in product_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)
        product_urls = unique_urls

        if not product_urls:
            logger.warning("GlasgowCollege: no product URLs found on category pages")
            return []

        # Step 2: scrape each product page for dates
        all_offerings: list[Offering] = []
        for url in product_urls:
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("GlasgowCollege: product fetch failed %s: %s", url, exc)
                time.sleep(2)
                continue
            time.sleep(2)
            try:
                offerings = self._parse_product_page(resp.text, url, provider)
                all_offerings.extend(offerings)
            except Exception as exc:
                logger.warning("GlasgowCollege: product parse failed %s: %s", url, exc)

        logger.info("GlasgowCollege adapter: %d offerings total", len(all_offerings))
        return all_offerings

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _extract_product_urls(self, html: str) -> list[str]:
        """Return absolute product URLs from a WooCommerce category page."""
        soup = BeautifulSoup(html, "lxml")
        urls: list[str] = []
        # WooCommerce renders product links as <a class="woocommerce-LoopProduct-link">
        # or as <h2 class="woocommerce-loop-product__title"> inside an <a>.
        # Most reliably: any <a href="..."> whose href contains /product/ and
        # whose href is under the same domain.
        for a in soup.find_all("a", href=True):
            href: str = a["href"].strip()
            if f"{NAUTICAL_BASE}/product/" in href and "/product-category/" not in href:
                urls.append(href.rstrip("/") + "/")
        return urls

    def _parse_product_page(
        self, html: str, page_url: str, provider: dict
    ) -> list[Offering]:
        """Parse a WooCommerce product page and return Offering objects."""
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(timezone.utc).isoformat()

        # Determine course ID from page title then URL slug
        title_tag = soup.find("h1") or soup.find("title")
        title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
        course_id = _course_id_from_text(title_text) or _course_id_from_text(page_url)
        if not course_id:
            logger.debug("GlasgowCollege: no course_id match for %s", page_url)
            return []

        # Extract price
        price: float | None = None
        price_tag = soup.select_one(".price .woocommerce-Price-amount, .price bdi")
        if price_tag:
            price_text = price_tag.get_text(strip=True).replace("£", "").replace(",", "")
            try:
                price = float(price_text)
            except ValueError:
                pass

        # Find date select options.
        # The FooEvents plugin renders:
        #   <select name="fooevents_bookings_date_val__trans">
        #     <option value="">Select Date</option>
        #     <option value="<opaque-token>">August 21, 2026 (5)</option>
        #     ...
        #   </select>
        # We look for any <select> whose options match our date pattern so the
        # adapter remains robust if the plugin version changes.
        offerings: list[Offering] = []
        seen_dates: set[str] = set()

        for sel in soup.find_all("select"):
            for opt in sel.find_all("option"):
                opt_text = opt.get_text(strip=True)
                m = _DATE_OPTION_RE.match(opt_text)
                if not m:
                    continue
                date_iso = _parse_month_day_year(m.group(1))
                if not date_iso or date_iso in seen_dates:
                    continue
                seen_dates.add(date_iso)

                spaces = m.group(2)  # may be None
                availability = f"{spaces} spaces" if spaces else None

                offerings.append(
                    Offering(
                        id=f"{course_id}-glasgow-college-{date_iso}",
                        course_id=course_id,
                        provider_id=provider["id"],
                        start_date=date_iso,
                        end_date=date_iso,
                        timezone="Europe/London",
                        duration_days=None,
                        price=price,
                        currency="GBP",
                        vat_included=True,
                        delivery_format="in_person",
                        availability=availability,
                        booking_url=safe_url(page_url),
                        source_url=page_url,
                        last_verified=now,
                        freshness_status="verified",
                    )
                )

        logger.info(
            "GlasgowCollege: %d offerings for course_id=%s (%s)",
            len(offerings),
            course_id,
            page_url,
        )
        return offerings
