"""City of Glasgow College — STCW short-course adapter.

The public-facing website is https://www.cityofglasgowcollege.ac.uk/.
Actual course bookings are handled by the dedicated WooCommerce/FooEvents
subdomain https://nautical.cityofglasgowcollege.ac.uk/, which the
GlasgowCollegeAdapter already scrapes.

This adapter is the canonical entry-point for providers whose ``website``
field contains ``cityofglasgowcollege.ac.uk``.  It delegates all fetching
to GlasgowCollegeAdapter so that scraping logic lives in exactly one place.

robots.txt summary for www.cityofglasgowcollege.ac.uk
------------------------------------------------------
Crawl-delay: 10 s (we honour >= 2 s delays, which is well within courtesy).
Disallowed paths relevant to this adapter: none — /work-with-us/ and the
nautical subdomain are not restricted.

See glasgow_college.py for the full implementation details and notes on
the FooEvents booking widget and WooCommerce product-category pagination.
"""
import logging

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.adapters.glasgow_college import GlasgowCollegeAdapter

logger = logging.getLogger(__name__)


class CityOfGlasgowAdapter(BaseAdapter):
    """Adapter for City of Glasgow College (cityofglasgowcollege.ac.uk).

    Delegates all HTTP fetching and HTML parsing to GlasgowCollegeAdapter,
    which targets the nautical.cityofglasgowcollege.ac.uk booking store.
    """

    def __init__(self) -> None:
        self._delegate = GlasgowCollegeAdapter()

    def fetch(self, provider: dict) -> list[Offering]:
        """Return STCW offerings for *provider* from the nautical booking portal."""
        logger.info(
            "CityOfGlasgowAdapter: fetching for provider_id=%s", provider.get("id")
        )
        return self._delegate.fetch(provider)
