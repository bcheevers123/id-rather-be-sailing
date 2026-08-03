"""Adapter for Warsash Maritime School (Solent University Southampton).

The course-availability page is Next.js rendered, but the underlying data is
served by an AccessPlan XML API that can be fetched directly without a browser:

  GET /accessplan/services/WebIntegration.asmx/GetCoursesPackage
      ?companyID={ID}&venueIDs=&categoryIDs=&courseIDs=

Two company IDs are used: SOLENTKQJZ (main STCW/safety courses) and
SOLENTUELG (simulation/piloting — not STCW).  We query both and merge.

The XML response contains <WICourse> elements (catalogue) and <WICourseDate>
elements (scheduled runs with start/end dates, price, booking URL).

Strategy:
1. Try the AccessPlan XML API directly (no browser required).
2. If both company IDs return empty <Courses/>, fall back to Playwright
   rendering and parse whatever date/price markup is present in the HTML.
"""
import logging
import re
import time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from pipeline.adapters.base import Offering
from pipeline.adapters.playwright_base import PlaywrightAdapter
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; +https://github.com/bcheevers123/id-rather-be-sailing)"

COURSE_AVAILABILITY_URL = "https://maritime.solent.ac.uk/courses/course-availability"
_API_BASE = "https://maritime.solent.ac.uk/accessplan/services/WebIntegration.asmx/GetCoursesPackage"
_COMPANY_IDS = ["SOLENTKQJZ", "SOLENTUELG"]

# AccessPlan XML namespace
_NS = "AccessPlanIT.Accessplan.Web.Services"

# Map AccessPlan course labels → MCA course_ids.
# More specific entries first to avoid substring ambiguity.
_LABEL_TO_COURSE_ID: list[tuple[str, str]] = [
    ("STCW Basic Safety Training", "bsw"),
    ("Basic Safety Training Week", "bsw"),
    ("Updated Proficiency in Personal Survival Techniques", "upst"),
    ("Updating Personal Survival Techniques", "upst"),
    ("Personal Survival Techniques", "pst"),
    ("Updated Proficiency in Advanced Fire Fighting", "uaff"),
    ("Updated Proficiency - Advanced Fire Fighting", "uaff"),
    ("Updating Advanced Fire Fighting", "uaff"),
    ("Updated Proficiency in Fire Prevention and Fire Fighting", "ufpff"),
    ("Updated Proficiency - Fire Prevention", "ufpff"),
    ("Updating Fire Prevention", "ufpff"),
    ("Training in Advanced Firefighting", "aff"),
    ("Advanced Fire Fighting", "aff"),
    ("Fire Prevention and Fire Fighting", "fpff"),
    ("Fire Prevention and Firefighting", "fpff"),
    ("Fire Prevention", "fpff"),
    ("Elementary First Aid", "efa"),
    ("Personal Safety and Social Responsibilit", "pssr"),
    ("Personal Safety and Social Responsibil", "pssr"),
    ("Updated Proficiency - Survival Craft", "upscrb"),
    ("Updated Proficiency in Survival Craft", "upscrb"),
    ("Updating Proficiency in Survival Craft", "upscrb"),
    ("Proficiency in Survival Craft and Rescue Boats", "pscrb"),
    ("Proficiency in Medical First Aid", "mfa"),
    ("Medical First Aid", "mfa"),
    ("Proficiency in Medical Care", "mc"),
    ("Fast Rescue Boat", "frb"),
    ("HELM Operational", "helm-o"),
    ("HELM Management", "helm-m"),
    ("Human Element, Leadership & Management at the Operational", "helm-o"),
    ("Human Element, Leadership & Management at the Management", "helm-m"),
    ("Human Element, Leadership and Management at the Operational", "helm-o"),
    ("Human Element, Leadership and Management at the Management", "helm-m"),
    ("Electronic Chart Display and Information Systems", "ecdis"),
    ("ECDIS", "ecdis"),
    ("GMDSS General Operator", "goc"),
    ("General Operator", "goc"),
    ("Security Awareness", "security-awareness"),
    ("Designated Security Duties", "dsd"),
    ("Ship Security Officer", "sso"),
]


def _map_label(label: str) -> str | None:
    """Return MCA course_id for a given AccessPlan course label, or None."""
    for substring, course_id in _LABEL_TO_COURSE_ID:
        if substring.lower() in label.lower():
            return course_id
    return None


def _ns(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


class SolentAdapter(PlaywrightAdapter):
    """Fetches STCW course dates from Warsash / Solent University.

    Uses the AccessPlan XML API directly; falls back to Playwright if the API
    returns empty data (e.g. if the API moves behind auth).
    """

    def fetch(self, provider: dict) -> list[Offering]:
        offerings = self._fetch_via_api(provider)
        if offerings:
            return offerings

        logger.info("Solent: AccessPlan API returned no data — trying Playwright fallback")
        html = self.fetch_rendered(
            COURSE_AVAILABILITY_URL,
            wait_selector="table",
            timeout=30000,
        )
        if html:
            return self._parse_html_fallback(html, provider)

        logger.warning("Solent: both API and Playwright fallback returned no data")
        return []

    # ------------------------------------------------------------------
    # Primary path: AccessPlan XML API
    # ------------------------------------------------------------------

    def _fetch_via_api(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": COURSE_AVAILABILITY_URL,
        })

        all_courses: dict[str, dict] = {}   # courseID → {label, cost, currency}
        all_dates: list[dict] = []

        for company_id in _COMPANY_IDS:
            url = (
                f"{_API_BASE}?companyID={company_id}"
                "&venueIDs=&categoryIDs=&courseIDs="
            )
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Solent AccessPlan fetch failed (companyID=%s): %s", company_id, e)
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                courses, dates = _parse_api_xml(resp.content)
                all_courses.update(courses)
                all_dates.extend(dates)
            except Exception as e:
                logger.warning("Solent AccessPlan parse failed (companyID=%s): %s", company_id, e)

        if not all_courses:
            return []

        return _build_offerings(all_courses, all_dates, provider, COURSE_AVAILABILITY_URL)

    # ------------------------------------------------------------------
    # Fallback path: rendered HTML (basic date/price scan)
    # ------------------------------------------------------------------

    def _parse_html_fallback(self, html: str, provider: dict) -> list[Offering]:
        from bs4 import BeautifulSoup
        from dateutil import parser as dateutil_parser

        soup = BeautifulSoup(html, "lxml")
        offerings: list[Offering] = []
        now = datetime.now(timezone.utc).isoformat()
        date_re = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")
        price_re = re.compile(r"[£\xA3]\s*([\d,]+(?:\.\d{2})?)")
        seen: set[str] = set()

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            for cell in cells:
                text = cell.get_text(strip=True)
                m = date_re.search(text)
                if not m:
                    continue
                try:
                    d = dateutil_parser.parse(m.group(), fuzzy=False).date().isoformat()
                except Exception:
                    continue
                if d in seen:
                    continue
                seen.add(d)
                pm = price_re.search(row.get_text())
                price = float(pm.group(1).replace(",", "")) if pm else None
                link = row.find("a", href=True)
                offerings.append(Offering(
                    id=f"unknown-solent-{d}",
                    course_id="unknown",
                    provider_id=provider["id"],
                    start_date=d,
                    end_date=d,
                    timezone="Europe/London",
                    duration_days=None,
                    price=price,
                    currency="GBP" if price else None,
                    vat_included=None,
                    delivery_format="in_person",
                    availability=None,
                    booking_url=safe_url(link["href"] if link else COURSE_AVAILABILITY_URL),
                    source_url=COURSE_AVAILABILITY_URL,
                    last_verified=now,
                    freshness_status="verified",
                ))
                break

        logger.info("Solent HTML fallback extracted %d offerings", len(offerings))
        return offerings


# ------------------------------------------------------------------
# XML helpers (module-level for testability)
# ------------------------------------------------------------------

def _parse_api_xml(content: bytes) -> tuple[dict, list]:
    """Parse AccessPlan XML. Returns (courses_dict, dates_list)."""
    root = ET.fromstring(content)

    courses: dict[str, dict] = {}
    courses_el = root.find(_ns("Courses"))
    if courses_el is not None:
        for course in courses_el.findall(_ns("WICourse")):
            cid = _text(course, "CourseID")
            label = _text(course, "Label") or ""
            cost_str = _text(course, "Cost")
            currency = _text(course, "Currency") or "GBP"
            try:
                cost = float(cost_str) if cost_str else None
            except ValueError:
                cost = None
            if cid:
                courses[cid] = {"label": label, "cost": cost, "currency": currency}

    dates: list[dict] = []
    dates_el = root.find(_ns("Dates"))
    if dates_el is not None:
        for date_el in dates_el.findall(_ns("WICourseDate")):
            cid = _text(date_el, "CourseID")
            start = _text(date_el, "StartDate")
            end = _text(date_el, "EndDate")
            status = _text(date_el, "Status") or ""
            booking_url = _text(date_el, "BookNowURL")
            cost_str = _text(date_el, "Cost")
            currency = _text(date_el, "Currency") or "GBP"
            date_id = _text(date_el, "CourseDateID") or ""
            try:
                cost = float(cost_str) if cost_str else None
            except ValueError:
                cost = None
            if cid and start:
                dates.append({
                    "course_id": cid,
                    "start": start,
                    "end": end or start,
                    "status": status,
                    "booking_url": booking_url,
                    "cost": cost,
                    "currency": currency,
                    "date_id": date_id,
                })

    return courses, dates


def _build_offerings(
    courses: dict,
    dates: list,
    provider: dict,
    source_url: str,
) -> list[Offering]:
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    for date_rec in dates:
        status = date_rec["status"].lower()
        if status == "cancelled":
            continue

        cid = date_rec["course_id"]
        course = courses.get(cid)
        if not course:
            continue

        label = course["label"]
        mca_course_id = _map_label(label)
        if not mca_course_id:
            continue

        try:
            start_date = datetime.fromisoformat(date_rec["start"]).date().isoformat()
            end_date = datetime.fromisoformat(date_rec["end"]).date().isoformat()
        except Exception:
            continue

        offering_key = f"{mca_course_id}-{start_date}-{cid}"
        if offering_key in seen:
            continue
        seen.add(offering_key)

        # Date-level cost takes precedence over course-level cost.
        price = date_rec["cost"] if date_rec["cost"] is not None else course["cost"]
        currency = date_rec["currency"] or course["currency"] or "GBP"
        booking_url = safe_url(date_rec["booking_url"])

        offerings.append(Offering(
            id=f"{mca_course_id}-solent-{start_date}-{date_rec['date_id']}",
            course_id=mca_course_id,
            provider_id=provider["id"],
            start_date=start_date,
            end_date=end_date,
            timezone="Europe/London",
            duration_days=None,
            price=price,
            currency=currency if price is not None else None,
            vat_included=None,
            delivery_format="in_person",
            availability=None,
            booking_url=booking_url,
            source_url=source_url,
            last_verified=now,
            freshness_status="verified",
        ))

    logger.info("Solent adapter built %d offerings from AccessPlan data", len(offerings))
    return offerings


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(_ns(tag))
    if child is None or child.text is None:
        return None
    return child.text.strip()
