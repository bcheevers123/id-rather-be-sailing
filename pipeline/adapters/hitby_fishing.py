"""Hit By Fishing School (Whitby & District Fishing Industry Training School) adapter.

DOMAIN NOTE:
    The configured URL https://www.hitbyfishingschool.co.uk does NOT resolve —
    "hitby" is a typo for "whitby". The correct domain is:
        https://www.whitbyfishingschool.co.uk/
    That domain issues a 302 redirect to:
        https://www.54northmaritime.co.uk/
    which is the organisation's rebranded website (54 North Maritime Training,
    Whitby, North Yorkshire).

SCRAPEABILITY (assessed 2026-08-04):
    NOT SCRAPEABLE — no machine-readable schedule exists.

    The site exposes four STCW course pages:
        /courses/stcw-personal-survival-techniques/           (PST,  £180)
        /courses/stcw-elementary-first-aid/                   (EFA,  £180)
        /courses/stcw-personal-safety-and-social-responsibilities-pssr/ (PSSR, £140)
        /courses/stcw-proficiency-in-security-awareness-psa/  (PSA,  £140)

    Each page contains a single stale date string "13/05/2024" which is the
    WordPress post-publication date, NOT a course run date.  No upcoming dates,
    no date table, no calendar widget, no JavaScript-loaded schedule data and
    no open API endpoint are present.  Booking requires submitting an "Enquire
    Now" contact form or telephoning 01947 825871.

    An advisory banner reads: "Basic Safety and Skippers Ticket courses coming
    soon, BOOK NOW!" confirming that scheduled dates are not yet published.

ACTION REQUIRED:
    Monitor https://www.54northmaritime.co.uk/candidates/mca-stcw/ periodically.
    When actual run dates appear in the HTML, update this adapter to parse them.
"""
import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

# True canonical URL (follows redirect from whitbyfishingschool.co.uk)
_MCA_STCW_URL = "https://www.54northmaritime.co.uk/candidates/mca-stcw/"


class HitbyFishingAdapter(BaseAdapter):
    """Adapter for Whitby & District Fishing Industry Training School (54 North Maritime).

    Returns an empty list until the provider publishes a machine-readable
    course schedule on their website.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        logger.info(
            "HitbyFishingAdapter: provider %s has no scrapeable schedule at %s "
            "(site redirects to %s). Returning empty list.",
            provider.get("id"),
            provider.get("website"),
            _MCA_STCW_URL,
        )
        return []
