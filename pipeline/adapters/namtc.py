"""New Alliance Marine Training Centre adapter (Wuhan/Qingdao/Shanghai, China).

namtc.com.cn — 湖北新海联船员培训有限公司
(Hubei Xinhailian Seafarer Training Co., Ltd.)

robots.txt: ``Allow: /`` — no restrictions.

Schedule availability: The site is hosted on the Chinese wanwang.xin SaaS
website-builder platform. All page content is delivered exclusively as
JavaScript (``document.write('...')`` calls loaded from cdn-static JS files).
A standard HTTP request returns only a shell HTML page with two ``<script>``
src tags pointing to the CDN. The actual content—including any course
schedule information—is rendered client-side by those scripts and is not
accessible without a full JavaScript execution environment (e.g. Playwright).

Course information is published ad-hoc via news articles (``/newsinfo/...``),
written in Chinese and listing internal Chinese Maritime Administration (CMA)
certification classes (T11 IGF Basic, T12 IGF Advance, etc.) that do not
correspond to the GOC/ROC/LRC/PST/FPFF/EFA/PSSR/PSCRB/AFF/MFA/MC/FRB
course IDs tracked by this system.

Since no structured, machine-readable public schedule exists on static HTML
pages, this adapter returns an empty list. If the provider gains a public
API or a server-side-rendered schedule page in future, update ``_fetch_impl``
and return populated Offering objects.
"""
import logging

from pipeline.adapters.base import BaseAdapter, Offering

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.namtc.com.cn/News_Events"


class NamtcAdapter(BaseAdapter):
    """Adapter for New Alliance Marine Training Centre (Wuhan/Qingdao/Shanghai, China).

    Returns [] because the site delivers all content via client-side JavaScript
    and publishes no structured public schedule accessible to a plain HTTP
    scraper.  No CAPTCHA bypassing or authentication is attempted.
    """

    def fetch(self, provider: dict) -> list[Offering]:
        """Return an empty list — no public structured schedule is available.

        The site (namtc.com.cn) uses the wanwang.xin SaaS builder which
        serves all page content exclusively through ``document.write()``
        JavaScript blocks loaded from an external CDN.  Parsing those scripts
        yields only informal news posts written in Chinese that announce
        Chinese Maritime Administration certificate courses (T11/T12 IGF
        classes) — none of which map to the GOC/ROC/LRC/STCW safety-course
        IDs tracked by this system.

        To scrape this site in future, a Playwright-based approach would be
        needed, combined with a Chinese-to-course-ID mapping for CMA classes.
        """
        logger.info(
            "NamtcAdapter: no public structured schedule available for %s; returning []",
            provider.get("id", "unknown"),
        )
        return []
