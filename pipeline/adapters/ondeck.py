"""Ondeck Maritime Training Antigua Ltd adapter.

The course schedule is served by a takeabyte.co.uk booking portal protected by
reCAPTCHA Enterprise and ASP.NET Core anti-forgery tokens.

Strategy (Playwright – JavaScript injection in headed Chrome):
  1. Navigate to the Ondeck takeabyte gateway and click "Next" (course list).
  2. For each STCW course, inject JavaScript that:
       a. Calls ``grecaptcha.enterprise.execute`` to get a real reCAPTCHA token.
       b. POSTs to ``Wm_getFirstAvailableDate`` → returns the first run month.
       c. POSTs to ``Wm_getAvailableCalDates`` with that month → returns dates.
     All three calls happen inside a single ``page.evaluate`` so the CSRF token
     and session cookies are available in the page context.
  3. The response is a JSON array:
       [{"calDate": "2026-09-01", "cssClass": "calLink"}, ...]
     Consecutive dates are grouped into runs (start_date = min, end_date = max).

reCAPTCHA note:
  reCAPTCHA Enterprise validates browser signals (history, cookies, account state).
  A freshly-launched Playwright Chrome window tends to receive a low score even
  when headed.  For production use, point ``ONDECK_CHROME_PROFILE`` at your real
  Chrome user-data directory so the browser carries established Google cookies::

      ONDECK_CHROME_PROFILE="C:/Users/YourName/AppData/Local/Google/Chrome/User Data"

  Without a profile the adapter still runs but may get 0 results.
  Set ``ONDECK_HEADLESS=1`` to override the headed default (expect zero results
  in headless environments without Xvfb and a valid profile).
"""
import logging
import os
import time
from datetime import date, datetime, timezone

from pipeline.adapters.base import BaseAdapter, Offering
from pipeline.normalise import safe_url

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; IdRatherBeSailing/1.0; "
    "+https://github.com/bcheevers123/id-rather-be-sailing)"
)

GATEWAY_URL = (
    "https://www.takeabyte.co.uk/InContact/public/gateway.aspx"
    "?func_id=79A2A98E7C95DA57&obc_id=8F89D1B294B9A78D"
)
SOURCE_URL = "https://www.ondecksailing.com/stcw-courses/"
TZ = "America/Antigua"
DIARY_ID = "3018"  # Ondeck Maritime Training Antigua

# STCW courses offered by Ondeck Maritime Training Antigua.
# Tuple: (etp_eventtype_id, display_name, canonical_course_id, num_days)
# etp_eventtype_id values captured from live booking-page DOM, August 2026.
_STCW_COURSES: list[tuple[str, str, str, int]] = [
    ("12634", "MCA Basic Safety Training Full Course STCW10", "bst", 5),
    ("12576", "MCA Elementary First Aid (STCW)", "efa", 1),
    ("12578", "MCA Fire Prevention & Fire Fighting (STCW)", "fpff", 1),
    ("12610", "MCA Personal Safety and Social Responsibilities (STCW)", "pssr", 1),
    ("12601", "MCA Personal Survival Techniques (STCW)", "pst", 1),
    ("17772", "MCA Medical First Aid Aboard Ships (MFAS)", "mfa", 4),
    ("17773", "MCA Medical Care Aboard Ships (MCAS)", "mc", 5),
]

# JavaScript injected into the page to fetch course dates without triggering the
# full wizard UI flow.  Returns a JSON-serialisable result object.
_FETCH_DATES_JS = """
async ([etp_id, diary_id, site_key]) => {
    const base = window.location.href + '&deviceType=desktop&handler=';
    const rvt = (document.querySelector("input[name='__RequestVerificationToken']") || {}).value || '';
    const headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'x-requested-with': 'XMLHttpRequest',
        'requestverificationtoken': rvt
    };

    // Step A: get first available date (which month to query)
    let firstDate = null;
    try {
        const tok1 = await grecaptcha.enterprise.execute(site_key, {action: 'firstAvailableDate'});
        const f1 = new URLSearchParams({
            eventtype_id: etp_id, diary_id, spaces_booked: '1',
            gToken: tok1, gSiteKey: site_key
        });
        const r1 = await fetch(base + 'Wm_getFirstAvailableDate',
            {method: 'POST', headers, body: f1.toString(), credentials: 'include'});
        const d1 = await r1.json();
        firstDate = d1.update_returnValue || null;
    } catch(e) {
        return {error: 'firstAvailableDate: ' + String(e).slice(0, 80)};
    }

    if (!firstDate) return {dates: [], reason: 'no upcoming sessions'};

    // Step B: get all calendar dates for the run month
    const dt = new Date(firstDate);
    const sdate = dt.toLocaleString('en-US', {month: 'long'}) + ' ' + dt.getFullYear();
    let calDates = [];
    try {
        const tok2 = await grecaptcha.enterprise.execute(site_key, {action: 'showCalendar'});
        const f2 = new URLSearchParams({
            sdate, eventtype_id: etp_id, diary_id, spaces_booked: '1',
            option_filter: '0', gToken: tok2, gSiteKey: site_key
        });
        const r2 = await fetch(base + 'Wm_getAvailableCalDates',
            {method: 'POST', headers, body: f2.toString(), credentials: 'include'});
        calDates = await r2.json();
    } catch(e) {
        return {error: 'getAvailableCalDates: ' + String(e).slice(0, 80)};
    }

    return {dates: calDates};
}
"""


def _group_dates(cal_dates: list[str]) -> list[tuple[str, str]]:
    """Cluster consecutive ISO date strings into (start, end) runs."""
    if not cal_dates:
        return []
    sorted_dates = sorted(date.fromisoformat(d) for d in cal_dates)
    runs: list[tuple[str, str]] = []
    run_start = sorted_dates[0]
    prev = sorted_dates[0]
    for d in sorted_dates[1:]:
        if (d - prev).days > 1:
            runs.append((run_start.isoformat(), prev.isoformat()))
            run_start = d
        prev = d
    runs.append((run_start.isoformat(), prev.isoformat()))
    return runs


class OndeckAdapter(BaseAdapter):
    """Fetch STCW course offerings from Ondeck Maritime Training Antigua."""

    def fetch(self, provider: dict) -> list[Offering]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.warning(
                "Ondeck: playwright is not installed — cannot scrape. "
                "Install with: pip install playwright && python -m playwright install chromium"
            )
            return []

        # Default headless=True for CI; set ONDECK_HEADLESS=0 locally if you need a visible browser.
        headless = os.environ.get("ONDECK_HEADLESS", "1") == "1"
        # Optionally use an existing Chrome profile for better reCAPTCHA scores.
        chrome_profile = os.environ.get("ONDECK_CHROME_PROFILE", "")

        all_offerings: list[Offering] = []

        try:
            with sync_playwright() as pw:
                launch_args = ["--disable-blink-features=AutomationControlled"]
                context_kwargs = dict(
                    user_agent=USER_AGENT,
                    locale="en-GB",
                )

                if chrome_profile:
                    # launch_persistent_context is required when passing user_data_dir
                    try:
                        context = pw.chromium.launch_persistent_context(
                            user_data_dir=chrome_profile,
                            headless=headless,
                            channel="chrome",
                            args=launch_args,
                            **context_kwargs,
                        )
                    except Exception:
                        context = pw.chromium.launch_persistent_context(
                            user_data_dir=chrome_profile,
                            headless=headless,
                            args=launch_args,
                            **context_kwargs,
                        )
                    browser = None
                else:
                    try:
                        browser = pw.chromium.launch(
                            headless=headless,
                            channel="chrome",
                            args=launch_args,
                        )
                    except Exception:
                        browser = pw.chromium.launch(
                            headless=headless,
                            args=launch_args,
                        )
                    context = browser.new_context(**context_kwargs)

                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )
                page = context.new_page()

                # Load the gateway once; all JS fetches run in this page context.
                try:
                    page.goto(GATEWAY_URL, timeout=30_000)
                    page.wait_for_load_state("networkidle", timeout=20_000)
                except Exception as e:
                    logger.warning("Ondeck: gateway load failed: %s", e)
                    context.close()
                    if browser:
                        browser.close()
                    return []
                time.sleep(2)

                # Click "Next" so the page JS initialises form fields (diary_id etc.)
                try:
                    page.locator("#onlineBooking_nextBtn").click(timeout=10_000)
                    page.wait_for_selector(
                        "tr.jqx_inputGridListBoxRow", timeout=15_000
                    )
                except Exception as e:
                    logger.warning("Ondeck: could not reach course list: %s", e)
                    context.close()
                    if browser:
                        browser.close()
                    return []

                # Wait for reCAPTCHA Enterprise client to initialise
                # (it registers asynchronously after page load)
                try:
                    page.wait_for_function(
                        "() => typeof grecaptcha !== 'undefined' && "
                        "typeof grecaptcha.enterprise !== 'undefined' && "
                        "typeof grecaptcha.enterprise.execute === 'function'",
                        timeout=15_000,
                    )
                except Exception:
                    logger.warning("Ondeck: reCAPTCHA Enterprise not ready — cannot scrape")
                    context.close()
                    if browser:
                        browser.close()
                    return []
                time.sleep(2)

                now_iso = datetime.now(timezone.utc).isoformat()

                for etp_id, display_name, course_id, num_days in _STCW_COURSES:
                    time.sleep(2)
                    try:
                        result = page.evaluate(
                            _FETCH_DATES_JS,
                            [etp_id, DIARY_ID, "6LdRwtwrAAAAAHJTuzAflAaoehtbCKwzEjYDCttK"],
                        )
                    except PWTimeout:
                        logger.warning(
                            "Ondeck: JS evaluation timeout for %s (%s)",
                            display_name,
                            etp_id,
                        )
                        continue
                    except Exception as e:
                        logger.warning(
                            "Ondeck: JS evaluation error for %s (%s): %s",
                            display_name,
                            etp_id,
                            e,
                        )
                        continue

                    if not isinstance(result, dict):
                        logger.debug("Ondeck: unexpected result type for %s: %r", display_name, result)
                        continue

                    if "error" in result:
                        logger.warning("Ondeck: API error for %s: %s", display_name, result["error"])
                        continue

                    if result.get("reason") == "no upcoming sessions":
                        logger.debug("Ondeck: no upcoming sessions for %s", display_name)
                        continue

                    dates_raw = result.get("dates", [])
                    if not dates_raw:
                        logger.debug("Ondeck: empty dates for %s", display_name)
                        continue

                    cal_dates = [
                        d["calDate"]
                        for d in dates_raw
                        if isinstance(d, dict) and d.get("cssClass") == "calLink"
                    ]
                    runs = _group_dates(cal_dates)

                    for start_date, end_date in runs:
                        offering_id = f"{course_id}-ondeck-{start_date}"
                        all_offerings.append(
                            Offering(
                                id=offering_id,
                                course_id=course_id,
                                provider_id=provider["id"],
                                start_date=start_date,
                                end_date=end_date,
                                timezone=TZ,
                                duration_days=float(num_days),
                                price=None,
                                currency=None,
                                vat_included=None,
                                delivery_format="in_person",
                                availability=None,
                                booking_url=safe_url(GATEWAY_URL),
                                source_url=SOURCE_URL,
                                last_verified=now_iso,
                                freshness_status="verified",
                            )
                        )
                        logger.debug(
                            "Ondeck: %s %s → %s … %s",
                            provider["id"],
                            course_id,
                            start_date,
                            end_date,
                        )

                context.close()
                if browser:
                    browser.close()

        except Exception as e:
            logger.warning("Ondeck: browser session failed: %s", e)
            return []

        if not all_offerings:
            logger.warning(
                "Ondeck: 0 offerings returned. "
                "If running headless, set ONDECK_HEADLESS=0 and ensure a display "
                "is available (reCAPTCHA Enterprise requires a real browser session)."
            )
        else:
            logger.info("Ondeck adapter: %d offerings total", len(all_offerings))

        return all_offerings
