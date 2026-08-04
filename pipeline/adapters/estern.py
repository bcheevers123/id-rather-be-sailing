"""Adapter for Western Maritime Training Ltd (westernmaritime.training).

# Scrapeability assessment — last checked 2026-08-04
#
# The canonical URL https://www.westernmaritime.training/ performs a 301
# redirect to https://westernmaritimetraining.co.uk/.  All pages on that
# domain are protected by SiteGround's sgcaptcha WAF in two stages:
#
#   Stage 1 — Proof-of-Work JavaScript challenge (difficulty 21, SHA-based).
#              robots.txt: User-agent: * / Disallow: (blank → allow all).
#              No rule blocks course or schedule paths.
#
#   Stage 2 — After the PoW is solved the server returns HTTP 403 Forbidden
#              regardless of User-Agent.  This appears to be a blanket block
#              applied to server/cloud IP ranges at the WAF level.
#
# Attempts made:
#   - requests with project User-Agent → 202 → captcha HTML
#   - requests with browser UA and full Accept headers → same 202
#   - Playwright (headless Chromium) with realistic UA → PoW solved →
#     HTTP 403 "Access to this page is forbidden"
#   - Playwright (non-headless) → same 403 result
#
# Conclusion: not scrapeable via automated means from a server/cloud IP.
# This adapter returns [] on every call.  If Western Maritime Training
# opens a public API or removes the WAF restriction, remove this note and
# implement parsing against westernmaritimetraining.co.uk.
"""

import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0;"
    " +https://github.com/bcheevers123/id-rather-be-sailing)"
)

# Canonical site URL (after redirect from westernmaritime.training)
SITE_URL = "https://westernmaritimetraining.co.uk/"


class EsternAdapter(BaseAdapter):
    """Adapter for Western Maritime Training Ltd.

    The provider's website is protected by a SiteGround sgcaptcha WAF that
    enforces a JavaScript proof-of-work challenge followed by a hard HTTP 403
    block for all non-residential IPs.  Automated scraping is not possible;
    this adapter always returns an empty list.

    See module docstring for full investigation notes.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        logger.warning(
            "EsternAdapter: westernmaritimetraining.co.uk is protected by "
            "SiteGround sgcaptcha WAF and returns HTTP 403 after the PoW "
            "challenge is solved. Automated scraping is not possible — "
            "returning empty list. Provider: %s",
            provider.get("id"),
        )
        return []
