"""Orkney College UHI adapter.

Investigation summary (2026-08-04)
===================================
orkney.uhi.ac.uk hosts Orkney College UHI (providers: orkney-college,
orkney-college-2, orkney-college-3).  The providers.json address mentions a
"Department of Maritime Studies, Victoria Street, Stromness" but the live
website carries no publicly accessible STCW course schedule.

robots.txt: HTTP 404 — no crawl restrictions in place.

Pages checked:
  - /courses/                               → no maritime courses
  - /business-and-community/short-courses/  → Business & Management, First Aid,
                                             Health & Safety, Hospitality,
                                             Leisure, Vehicle/Plant Operator
  - /search?q=STCW                          → 0 results
  - /search?q=maritime                      → 0 results
  - /business-and-community/short-courses/first-aid/  → workplace first aid only
  - /business-and-community/short-courses/health-safety/ → IOSH / grounds maint.
  - /business-and-community/short-courses/leisure-courses/ → dry stone dyking;
    site states it is "looking to develop" leisure courses

No STCW, MCA-approved, sea survival, fire fighting, or any other maritime
safety short course is publicly listed on the site.  This adapter therefore
returns an empty list.  If Orkney College UHI publishes a public STCW schedule
in future, revisit /business-and-community/short-courses/ or contact
ocshortcourses@uhi.ac.uk / 01856 569000.
"""

import logging
from datetime import datetime, timezone

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

SOURCE_URL = "https://www.orkney.uhi.ac.uk/business-and-community/short-courses/"


class OrkneyUhiAdapter(BaseAdapter):
    """Adapter for Orkney College UHI (orkney.uhi.ac.uk).

    Returns an empty list because the site publishes no public STCW course
    schedule.  See module docstring for full investigation notes.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return [] — no public STCW schedule found on orkney.uhi.ac.uk."""
        logger.info(
            "OrkneyUhiAdapter: no public STCW schedule on orkney.uhi.ac.uk "
            "(provider=%s) — returning []",
            provider.get("id"),
        )
        return []
