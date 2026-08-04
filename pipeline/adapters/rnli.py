"""RNLI (Royal National Lifeboat Institution) adapter.

**Why this adapter returns []**

Every HTTP request to rnli.org — including robots.txt, the training index,
individual course pages, and the sitemap — returns HTTP 403 Forbidden.  The
site uses a CDN/WAF (likely Cloudflare or equivalent) that blocks all
non-browser User-Agents at the network edge, regardless of User-Agent string.

Attempts made (all returned 403):
  - https://www.rnli.org/robots.txt
  - https://rnli.org/robots.txt
  - https://www.rnli.org/training
  - https://www.rnli.org/training/sea-survival
  - https://www.rnli.org/training/safety-training-for-sea-users/stcw-sea-survival
  - https://www.rnli.org/sitemap.xml

Because we cannot retrieve robots.txt we treat the site as implicitly blocking
automated access.  No fabricated data is returned.

To re-enable this adapter:
  1. Obtain explicit written permission from RNLI commercial_training@rnli.org.uk
     and any required API credentials or a whitelisted IP range.
  2. Replace the stub body below with a real scraping implementation.
"""

import logging
from datetime import datetime, timezone

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

# Training landing page — referenced as source_url in any future implementation.
TRAINING_URL = "https://www.rnli.org/training"

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)


class RnliAdapter(BaseAdapter):
    """Stub adapter for the Royal National Lifeboat Institution (RNLI).

    Returns an empty list because rnli.org blocks all programmatic access with
    HTTP 403 at the CDN/WAF layer.  See module docstring for full details.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        logger.info(
            "RnliAdapter: rnli.org returns HTTP 403 on all paths; "
            "returning [] for provider %s",
            provider.get("id"),
        )
        # No network requests are made — the site is not publicly scrapable.
        return []
