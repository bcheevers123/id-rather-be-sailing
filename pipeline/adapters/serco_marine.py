"""Serco Marine Services adapter.

Scout result (2026-08-04): sercomarine.com is a parked/reserved domain.
Every URL at www.sercomarine.com (including /robots.txt) returns a global
HTTP 301 redirect to an Azure DNS holding page at
  https://sra3pmwebdnsholdingpage.z33.web.core.windows.net/
which displays only: "This domain is reserved by Serco. You will now be
automatically redirected to serco.com."

There is no course schedule, robots.txt, or any scrapeable content at
sercomarine.com.  The parent site (serco.com) returns HTTP 403 for all
programmatic requests, and carries no STCW course schedule content.

Action required: manually locate Serco Marine's current training URL and
update SOURCE_URL below, then implement the scraping logic.  Until then this
adapter returns an empty list so the pipeline continues without errors.

Robots.txt: not served (domain redirects globally before robots.txt can be
reached).

STCW course IDs supported: pst, fpff, efa, pssr, pscrb, aff, mfa, mc, frb.

Provider IDs:
  serco-marine-services
  serco-marine-services-2
  serco-marine-services-3
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

# Update this URL once Serco Marine publishes a live training schedule page.
SOURCE_URL = "http://www.sercomarine.com/"

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

# Minimum polite delay between requests (seconds) — enforced when scraping
# is implemented.
_REQUEST_DELAY = 2.0


class SercoMarineAdapter(BaseAdapter):
    """Adapter for Serco Marine Services STCW courses.

    Returns an empty list because sercomarine.com is currently a reserved/
    parked domain with no published course schedule.  Re-implement once a
    live schedule URL is available.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return an empty list — no scrapeable schedule is available.

        sercomarine.com redirects globally to an Azure DNS holding page;
        no course dates are published at any known URL.
        """
        logger.info(
            "SercoMarine adapter: skipping provider %s — sercomarine.com is a "
            "parked domain with no published schedule (SOURCE_URL=%s)",
            provider.get("id"),
            SOURCE_URL,
        )
        return []
