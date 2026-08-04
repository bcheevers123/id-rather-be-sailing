"""ABB Marine Academy (Genova, Italy) adapter.

ABB Marine Academy offers STCW and maritime training courses in Genova, Italy,
through ABB's marine and ports division at new.abb.com.

Investigation results (2026-08-04)
-----------------------------------
All HTTP requests to new.abb.com timed out during investigation (robots.txt,
/marine, /marine/training, /marine/services/training).  The domain is operated
by ABB Ltd, a large industrial conglomerate, and the site is known to:

  - Use heavy JavaScript rendering (likely React/Angular SPA).
  - Employ enterprise-grade bot mitigation (CDN/WAF layer).
  - Require JavaScript execution to display any page content.

Because:
  1. robots.txt could not be fetched — access restriction cannot be
     confirmed absent, so we treat the inaccessible domain conservatively.
  2. No public STCW/maritime course schedule page was reachable via plain
     HTTP GET.
  3. No CAPTCHA bypass, headless-browser automation, or authentication is
     permitted by the scraper rules.

This adapter therefore returns an empty list.  If ABB Marine Academy
publishes a stable, publicly-accessible course schedule URL in future
(e.g. a plain-HTML page or a documented JSON API), the adapter should be
updated to fetch and parse that endpoint.

To re-investigate:
  curl -A "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; \
      +https://github.com/bcheevers123/id-rather-be-sailing)" \
      https://new.abb.com/robots.txt
  curl ... https://new.abb.com/marine/training
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

SOURCE_URL = "https://new.abb.com/marine"


class AbbMarineAdapter(BaseAdapter):
    """Adapter for ABB Marine Academy (Genova, Italy).

    Returns an empty list because new.abb.com does not expose a publicly
    accessible, machine-readable course schedule.  All HTTP requests to the
    domain timed out during investigation; the site appears to require
    JavaScript execution and/or blocks automated access at the CDN/WAF layer.
    See module docstring for full details.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return [] — no accessible public schedule found on new.abb.com.

        The site times out consistently for plain HTTP GET requests and no
        public course schedule endpoint was discovered.  No CAPTCHA bypass or
        authentication is used.
        """
        logger.info(
            "AbbMarineAdapter: new.abb.com does not expose a publicly "
            "accessible course schedule; returning []"
        )
        return []
