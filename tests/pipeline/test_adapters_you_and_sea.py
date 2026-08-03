from pathlib import Path
import responses
from pipeline.adapters.you_and_sea import YouAndSeaAdapter

FIXTURE = Path("tests/pipeline/fixtures/youandsea_course_calendar.html").read_text(encoding="utf-8")
SOURCE_URL = "https://youandsea.com/course-calendar"
PROVIDER = {"id": "you-and-sea-ltd", "official_name": "You & Sea Ltd", "website": "https://youandsea.com/"}


@responses.activate
def test_you_and_sea_fetch_returns_list():
    responses.add(responses.GET, SOURCE_URL, body=FIXTURE, status=200)
    adapter = YouAndSeaAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    assert isinstance(result, list)


@responses.activate
def test_you_and_sea_js_rendered_returns_empty():
    """Squarespace JS-rendered calendar has no date data in raw HTML."""
    responses.add(responses.GET, SOURCE_URL, body=FIXTURE, status=200)
    adapter = YouAndSeaAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    # The fixture is JS-rendered: no dates visible in server-sent HTML
    assert result == []


@responses.activate
def test_you_and_sea_http_error_returns_empty():
    responses.add(responses.GET, SOURCE_URL, status=503)
    adapter = YouAndSeaAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    assert result == []


@responses.activate
def test_you_and_sea_with_static_event_html():
    """If Squarespace returns SSR event markup the adapter extracts dates."""
    static_html = """
    <html><body>
    <article class="eventlist-event">
      <time datetime="2026-09-14T09:00:00">14 September 2026</time>
      <a href="https://youandsea.com/events/pst-sept">Book</a>
    </article>
    <article class="eventlist-event">
      <time datetime="2026-10-05T09:00:00">5 October 2026</time>
      <a href="https://youandsea.com/events/pst-oct">Book</a>
    </article>
    </body></html>
    """
    responses.add(responses.GET, SOURCE_URL, body=static_html, status=200)
    adapter = YouAndSeaAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    assert len(result) == 2
    assert result[0].start_date == "2026-09-14"
    assert result[1].start_date == "2026-10-05"
    assert result[0].course_id == "pst"
    assert result[0].provider_id == "you-and-sea-ltd"
    assert result[0].booking_url == "https://youandsea.com/events/pst-sept"
