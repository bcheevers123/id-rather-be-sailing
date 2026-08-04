"""Falmouth Marine School adapter — stub.

Investigation findings
----------------------
robots.txt (https://www.falmouthmarineschool.ac.uk/robots.txt) blocks several
AI-crawler user-agents but allows the * wildcard user-agent except for
/wp-admin/ and a handful of AJAX paths.  Our Mozilla/5.0 IdRatherBeSailing
user-agent is not blocked by robots.txt.

However, every URL on falmouthmarineschool.ac.uk — including the homepage,
/courses/, /short-courses/, /maritime-training/, and /sitemap.xml — returns
HTTP 403 Forbidden for non-browser requests.  The site appears to enforce a
browser-fingerprint or session-cookie requirement that cannot be satisfied
without a full browser engine.

No public schedule data is machine-readable via plain HTTP requests.

This adapter therefore performs no network activity and returns an empty list.
If the site changes to permit programmatic access in future, replace the stub
with a proper scraper using the techniques in `playwright_base.py`.
"""
import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)


class FalmouthMarineSchoolAdapter(BaseAdapter):
    """Stub adapter for Falmouth Marine School (falmouthmarineschool.ac.uk).

    The site returns HTTP 403 Forbidden for all programmatic requests.
    No course schedule data is accessible without a live browser session.
    Returns [] without making any network calls.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return empty list — falmouthmarineschool.ac.uk is not machine-readable.

        All page requests to falmouthmarineschool.ac.uk return HTTP 403
        Forbidden.  No scraping is attempted.
        """
        logger.info(
            "FalmouthMarineSchool: site returns 403 for all requests — "
            "returning empty list for provider %s",
            provider.get("id"),
        )
        return []
