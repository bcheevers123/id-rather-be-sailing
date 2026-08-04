"""Adapter for Fleetwood Nautical Campus (Blackpool and The Fylde College).

This adapter targets https://fleetwoodnautical.blackpool.ac.uk and scrapes
STCW course dates from the offshore STCW courses listing page and each
individual course page.

robots.txt check (2026-08-04): only restricts /admin/, /user/login, and
similar administrative paths. Public course pages are permitted.

The site uses a Drupal CMS. Each STCW course has its own page under
/course/oe1ec<NNN> containing a table of upcoming start dates, location,
duration/fee, and mailto enquiry links. No direct booking URL is exposed;
booking_url is set to None for all offerings.

Technique: HTTP GET with BeautifulSoup HTML parsing. Minimum 2-second delay
between requests enforced.
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.adapters.blackpool import (
    BlackpoolAdapter,
    _extract_course_links,   # noqa: F401  (re-exported for tests)
    _parse_course_page,      # noqa: F401  (re-exported for tests)
    STCW_COURSE_PAGE,        # noqa: F401  (re-exported for tests)
)

logger = logging.getLogger(__name__)


class FleetwoodAdapter(BaseAdapter):
    """Scrapes STCW course dates from Fleetwood Nautical Campus.

    Delegates to BlackpoolAdapter, which targets the same domain
    (fleetwoodnautical.blackpool.ac.uk). The two adapter names exist because
    the provider data contains entries registered under both the college name
    and the campus name; both resolve to the same website and scraping logic.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch STCW offerings for the given provider.

        Returns an empty list on any network or parse failure. Never fabricates
        dates or prices — only emits Offering objects when a real start date is
        found in the page HTML.
        """
        delegate = BlackpoolAdapter()
        offerings = delegate.fetch(provider)
        logger.info(
            "FleetwoodAdapter: fetched %d offerings for provider %r",
            len(offerings),
            provider.get("id"),
        )
        return offerings
