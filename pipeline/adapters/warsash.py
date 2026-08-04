"""Adapter for Warsash Maritime School (Solent University Southampton).

Website: https://maritime.solent.ac.uk
46 provider IDs share this domain (all start with
"warsash-maritime-school-solent-university-...").

robots.txt: The domain returns a Next.js SPA for /robots.txt (HTTP 200 HTML),
meaning no machine-readable robots.txt is in place.  The AccessPlan XML API
used below is a first-party booking integration endpoint linked from the
course-availability page itself and is freely accessible without authentication.

Technique: AccessPlan XML API (no browser required)
  GET /accessplan/services/WebIntegration.asmx/GetCoursesPackage
      ?companyID={ID}&venueIDs=&categoryIDs=&courseIDs=

Two company IDs serve different course groups:
  SOLENTKQJZ – main STCW / safety courses (~75 courses, ~650 date records)
  SOLENTUELG – simulation / piloting (not STCW)

The XML response contains <WICourse> elements (course catalogue) and
<WICourseDate> elements (scheduled runs with ISO start/end datetimes, price,
and a direct booking URL).

Minimum 2-second delay between requests is enforced.
"""
import logging
import re
import time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import requests

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

_COURSE_AVAILABILITY_URL = "https://maritime.solent.ac.uk/courses/course-availability"
_API_BASE = (
    "https://maritime.solent.ac.uk/accessplan/services/"
    "WebIntegration.asmx/GetCoursesPackage"
)
_COMPANY_IDS = ["SOLENTKQJZ", "SOLENTUELG"]

# AccessPlan XML namespace
_NS = "AccessPlanIT.Accessplan.Web.Services"


# Map AccessPlan course labels → project course_ids.
# More-specific substrings must appear before shorter ones to avoid false
# matches.  Case-insensitive matching is used in _map_label().
_LABEL_MAP: list[tuple[str, str]] = [
    # Basic Safety Training bundle
    ("STCW Basic Safety Training", "bst"),
    ("Basic Safety Training Week", "bst"),
    # PST / UPST
    ("Updated Proficiency in Personal Survival Techniques", "upst"),
    ("Updating Personal Survival Techniques", "upst"),
    ("Personal Survival Techniques", "pst"),
    # AFF / UAFF
    ("Updated Proficiency in Advanced Fire Fighting", "uaff"),
    ("Updated Proficiency - Advanced Fire Fighting", "uaff"),
    ("Updating Advanced Fire Fighting", "uaff"),
    ("Training in Advanced Firefighting", "aff"),
    ("Advanced Fire Fighting", "aff"),
    ("Advanced Firefighting", "aff"),
    # FPFF / UFPFF
    ("Updated Proficiency in Fire Prevention and Fire Fighting", "ufpff"),
    ("Updated Proficiency - Fire Prevention", "ufpff"),
    ("Updating Fire Prevention", "ufpff"),
    ("Fire Prevention and Fire Fighting", "fpff"),
    ("Fire Prevention and Firefighting", "fpff"),
    ("Fire Prevention", "fpff"),
    # EFA
    ("Elementary First Aid", "efa"),
    # PSSR
    ("Personal Safety and Social Responsibilit", "pssr"),
    # UPSCRB / PSCRB
    ("Updated Proficiency - Survival Craft", "upscrb"),
    ("Updated Proficiency in Survival Craft", "upscrb"),
    ("Updating Proficiency in Survival Craft", "upscrb"),
    ("Proficiency in Survival Craft and Rescue Boats", "pscrb"),
    # MFA / MC
    ("Proficiency in Medical First Aid", "mfa"),
    ("Medical First Aid", "mfa"),
    ("Proficiency in Medical Care", "mc"),
    ("Medical Care", "mc"),
    # FRB
    ("Proficiency in Fast Rescue Boats", "frb"),
    ("Fast Rescue Boat", "frb"),
]


def _map_label(label: str) -> str | None:
    """Return project course_id for an AccessPlan course label, or None."""
    low = label.lower()
    for substring, course_id in _LABEL_MAP:
        if substring.lower() in low:
            return course_id
    return None


def _ns(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


def _text(el: ET.Element, tag: str) -> str | None:
    child = el.find(_ns(tag))
    if child is None or child.text is None:
        return None
    return child.text.strip()


class WarsashAdapter(BaseAdapter):
    """Fetches STCW course dates from Warsash Maritime / Solent University via
    the AccessPlan XML API.

    The ``fetch`` method is called once per provider record; since all 46
    provider IDs share one booking system the API is only queried on the first
    call and the results are cached in-process for subsequent calls.
    """

    _cache: list[Offering] | None = None
    _cache_fetched_for: str | None = None  # provider_id of first caller

    def fetch(self, provider: dict) -> list[Offering]:
        # Return cached offerings (re-tagged with this provider's ID) on
        # repeated calls so we do not hammer the API 46 times per pipeline run.
        if WarsashAdapter._cache is not None:
            return self._retag(WarsashAdapter._cache, provider["id"])

        offerings = self._fetch_via_api(provider)
        WarsashAdapter._cache = offerings
        WarsashAdapter._cache_fetched_for = provider["id"]
        return offerings

    # ------------------------------------------------------------------
    # Primary fetch path: AccessPlan XML API
    # ------------------------------------------------------------------

    def _fetch_via_api(self, provider: dict) -> list[Offering]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Referer": _COURSE_AVAILABILITY_URL,
        })

        all_courses: dict[str, dict] = {}  # AccessPlan courseID → {label, cost, currency}
        all_dates: list[dict] = []

        for company_id in _COMPANY_IDS:
            url = (
                f"{_API_BASE}?companyID={company_id}"
                "&venueIDs=&categoryIDs=&courseIDs="
            )
            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "Warsash AccessPlan fetch failed (companyID=%s): %s",
                    company_id, exc,
                )
                time.sleep(2)
                continue
            time.sleep(2)

            try:
                courses, dates = _parse_api_xml(resp.content)
                all_courses.update(courses)
                all_dates.extend(dates)
            except Exception as exc:
                logger.warning(
                    "Warsash AccessPlan XML parse failed (companyID=%s): %s",
                    company_id, exc,
                )

        if not all_courses:
            logger.warning("Warsash: AccessPlan API returned no course data")
            return []

        return _build_offerings(all_courses, all_dates, provider)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _retag(offerings: list[Offering], provider_id: str) -> list[Offering]:
        """Return a copy of the cached offerings with a different provider_id."""
        result = []
        for o in offerings:
            result.append(Offering(
                id=re.sub(
                    r"-solent-",
                    "-warsash-",
                    o.id.replace(o.provider_id, provider_id),
                ),
                course_id=o.course_id,
                provider_id=provider_id,
                start_date=o.start_date,
                end_date=o.end_date,
                timezone=o.timezone,
                duration_days=o.duration_days,
                price=o.price,
                currency=o.currency,
                vat_included=o.vat_included,
                delivery_format=o.delivery_format,
                availability=o.availability,
                booking_url=o.booking_url,
                source_url=o.source_url,
                last_verified=o.last_verified,
                freshness_status=o.freshness_status,
            ))
        return result


# ------------------------------------------------------------------
# XML parsing helpers (module-level for testability)
# ------------------------------------------------------------------

def _parse_api_xml(content: bytes) -> tuple[dict, list]:
    """Parse AccessPlan GetCoursesPackage XML.

    Returns:
        courses: {AccessPlan courseID → {label, cost, currency}}
        dates:   list of date record dicts
    """
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
) -> list[Offering]:
    """Convert parsed AccessPlan data into Offering objects."""
    now = datetime.now(timezone.utc).isoformat()
    offerings: list[Offering] = []
    seen: set[str] = set()

    for date_rec in dates:
        if date_rec["status"].lower() == "cancelled":
            continue

        cid = date_rec["course_id"]
        course = courses.get(cid)
        if not course:
            continue

        mca_course_id = _map_label(course["label"])
        if not mca_course_id:
            continue

        try:
            start_date = datetime.fromisoformat(date_rec["start"]).date().isoformat()
            end_date = datetime.fromisoformat(date_rec["end"]).date().isoformat()
        except Exception:
            continue

        offering_key = f"{mca_course_id}-{start_date}-{cid}-{date_rec['date_id']}"
        if offering_key in seen:
            continue
        seen.add(offering_key)

        # Date-level cost takes precedence over course-level cost.
        price = (
            date_rec["cost"]
            if date_rec["cost"] is not None
            else course["cost"]
        )
        currency = date_rec["currency"] or course["currency"] or "GBP"
        booking_url = safe_url(date_rec["booking_url"])

        offerings.append(Offering(
            id=f"{mca_course_id}-warsash-{start_date}-{date_rec['date_id']}",
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
            source_url=_COURSE_AVAILABILITY_URL,
            last_verified=now,
            freshness_status="verified",
        ))

    logger.info(
        "Warsash adapter built %d offerings for provider %s",
        len(offerings),
        provider["id"],
    )
    return offerings
