"""Yacht Crew Training (yachtcrewtraining.com) adapter.

This is Seascope France's Antibes/French Riviera operation — a SEPARATE site
from seascopemaritimetraining.com which has its own adapter (seascope.py).

The site runs on Shopify.  All products are exposed through the public
Storefront JSON endpoint /products.json.  STCW courses appear as individual
Shopify products whose variants represent each available run date; the
variant option1 value is a human-readable date string such as:

    "04 September 2026"
    "31 August-04 September 2026"
    "31 August"          ← year omitted (assume current/next calendar year)

Prices are in GBP (the site default currency is GBP £).  All courses run in
Antibes, France.
"""
import logging
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from dateutil import parser as dateutil_parser

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

BASE_URL = "https://www.yachtcrewtraining.com"
PRODUCTS_JSON_URL = "https://www.yachtcrewtraining.com/products.json"

# Keywords in handle / title -> canonical course_id.
# Evaluated in order; first match wins.
# Packs (BST) map to "bst" which we store under each component; for the full
# BST pack we use "bst" as the course_id since it covers PST+FPFF+EFA+PSSR.
_COURSE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpst\b|personal.survival.technique", re.I), "pst"),
    (re.compile(r"\bfpff\b|fire.prevention.and.fire.fighting|fire-prevention-fire-fighting", re.I), "fpff"),
    (re.compile(r"\befa\b|elementary.first.aid", re.I), "efa"),
    (re.compile(r"\bpssr\b|personal.safety.and.social.responsibility|personal-safety-social-responsibility", re.I), "pssr"),
    (re.compile(r"\bpscrb\b|survival.craft", re.I), "pscrb"),
    (re.compile(r"\baff\b|advanced.fire.fighting", re.I), "aff"),
    (re.compile(r"\bmfa\b|medical.first.aid", re.I), "mfa"),
    (re.compile(r"\bmc\b|medical.care", re.I), "mc"),
    (re.compile(r"\bfrb\b|fast.rescue.boat", re.I), "frb"),
    # BST is the combined Basic Safety Training pack (PST+FPFF+EFA+PSSR)
    (re.compile(r"\bbst\b|basic.safety.training", re.I), "bst"),
]

# Variant titles to skip — not real dated offerings
_SKIP_TITLES = re.compile(
    r"^\s*(on.demand|available.on.demand|coming.soon|default.title|tbc)\s*$",
    re.I,
)


def _identify_course(handle: str, title: str) -> str | None:
    """Return canonical course_id or None if the product is not an STCW course."""
    text = f"{handle} {title}"
    for pattern, course_id in _COURSE_MAP:
        if pattern.search(text):
            return course_id
    return None


def _parse_date_range(variant_title: str) -> tuple[str, str] | None:
    """
    Parse a variant title into (start_date_iso, end_date_iso).

    Handles:
      - "04 September 2026"           -> single-day course
      - "31 August-04 September 2026" -> multi-day range
      - "31 August"                   -> year-less; infer nearest future year
      - "31 August 2026-04 September 2026"
    Returns None if the title cannot be parsed as a date.
    """
    title = variant_title.strip()

    # Skip known non-date values
    if _SKIP_TITLES.match(title):
        return None

    # Try to detect a date range separator: " - ", "–", "-" between two dates
    # Pattern: something date-like, a separator, something date-like
    # We split on " - " (with spaces) or "–" first, then bare "-"
    range_sep = re.compile(
        r"^(.+?)\s*(?:–|\s-\s)\s*(.+)$"
    )
    m = range_sep.match(title)
    if not m:
        # Try bare hyphen between day and rest-of-date, e.g. "31 August-04 September 2026"
        # Match: digits, optional space, (optional month), hyphen, digits...
        m2 = re.match(
            r"^(\d{1,2}\s+\w+(?:\s+\d{4})?)\s*-\s*(\d{1,2}\s+\w+(?:\s+\d{4})?)$",
            title,
        )
        if m2:
            start_str, end_str = m2.group(1), m2.group(2)
        else:
            start_str = title
            end_str = title
    else:
        start_str, end_str = m.group(1).strip(), m.group(2).strip()

    now = datetime.now(timezone.utc)

    def _try_parse(s: str, reference_year: int | None = None) -> datetime | None:
        if reference_year:
            s = s + f" {reference_year}"
        try:
            return dateutil_parser.parse(s, fuzzy=True, default=datetime(now.year, 1, 1))
        except Exception:
            return None

    start_dt = _try_parse(start_str)
    if start_dt is None:
        return None

    # If start date is in the past by more than 60 days and no year was given,
    # bump to next year
    if (now - start_dt.replace(tzinfo=timezone.utc)).days > 60 and str(now.year) not in start_str:
        start_dt = _try_parse(start_str, reference_year=now.year + 1)
        if start_dt is None:
            return None

    end_dt = _try_parse(end_str)
    if end_dt is None:
        end_dt = start_dt

    # End date must be >= start date; if end day < start day (e.g. month rolled),
    # dateutil may have parsed it in prior month — ensure it's >= start
    if end_dt < start_dt:
        end_dt = start_dt

    return start_dt.date().isoformat(), end_dt.date().isoformat()


class YachtCrewTrainingAdapter(BaseAdapter):
    """Adapter for https://www.yachtcrewtraining.com/ (Seascope France, Antibes)."""

    def fetch(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        # Fetch all products via Shopify's public JSON endpoint
        all_products = []
        page = 1
        page_size = 250
        while True:
            url = f"{PRODUCTS_JSON_URL}?limit={page_size}&page={page}"
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("YachtCrewTraining products.json fetch failed (page %d): %s", page, exc)
                break

            try:
                data = resp.json()
            except Exception as exc:
                logger.warning("YachtCrewTraining products.json parse failed (page %d): %s", page, exc)
                break

            batch = data.get("products", [])
            if not batch:
                break
            all_products.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
            time.sleep(2)

        if not all_products:
            logger.warning("YachtCrewTraining: no products found")
            return []

        time.sleep(2)

        now = datetime.now(timezone.utc).isoformat()
        all_offerings: list[Offering] = []
        seen: set[str] = set()

        for product in all_products:
            title = product.get("title", "")
            handle = product.get("handle", "")

            course_id = _identify_course(handle, title)
            if course_id is None:
                continue

            product_url = f"{BASE_URL}/products/{handle}"
            variants = product.get("variants", [])

            for variant in variants:
                variant_title: str = variant.get("title") or variant.get("option1") or ""
                if not variant_title:
                    continue

                parsed = _parse_date_range(variant_title)
                if parsed is None:
                    logger.debug(
                        "YachtCrewTraining: skipping unparseable variant '%s' on %s",
                        variant_title, handle,
                    )
                    continue

                start_date, end_date = parsed

                # Filter out obviously past dates
                try:
                    start_dt = datetime.fromisoformat(start_date)
                    if start_dt < datetime.now() and (datetime.now() - start_dt).days > 1:
                        logger.debug(
                            "YachtCrewTraining: skipping past date '%s' on %s",
                            start_date, handle,
                        )
                        continue
                except Exception:
                    pass

                # Price: Shopify returns price as string in GBP
                price_str = variant.get("price", "")
                try:
                    price = float(price_str) if price_str else None
                except ValueError:
                    price = None

                available = variant.get("available", True)
                availability = "available" if available else "sold_out"

                variant_id = variant.get("id", "")
                offering_id = f"{course_id}-yct-antibes-{start_date}-{variant_id}"

                if offering_id in seen:
                    continue
                seen.add(offering_id)

                # Build booking URL with variant selected
                booking_url = safe_url(
                    f"{product_url}?variant={variant_id}"
                ) if variant_id else safe_url(product_url)

                all_offerings.append(Offering(
                    id=offering_id,
                    course_id=course_id,
                    provider_id=provider["id"],
                    start_date=start_date,
                    end_date=end_date,
                    timezone="Europe/Paris",
                    duration_days=None,
                    price=price,
                    currency="GBP",
                    vat_included=None,
                    delivery_format="in_person",
                    availability=availability,
                    booking_url=booking_url,
                    source_url=product_url,
                    last_verified=now,
                    freshness_status="verified",
                ))

        logger.info(
            "YachtCrewTraining adapter extracted %d offerings from %d STCW products",
            len(all_offerings),
            sum(1 for p in all_products if _identify_course(p.get("handle", ""), p.get("title", "")) is not None),
        )
        return all_offerings
