from pathlib import Path
import responses
from pipeline.adapters.stream_marine import StreamMarineAdapter

FIXTURE = Path("tests/pipeline/fixtures/stream_marine_course_page.html").read_text(encoding="utf-8")
PROVIDER = {"id": "stream-marine-training", "official_name": "Stream Marine Training", "website": "https://streammarinetraining.com/"}
SOURCE_URL = "https://streammarinetraining.com/courses/"


@responses.activate
def test_stream_marine_fetch_returns_list():
    responses.add(responses.GET, SOURCE_URL, body=FIXTURE, status=200)
    adapter = StreamMarineAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    assert isinstance(result, list)


@responses.activate
def test_stream_marine_http_error_returns_empty():
    responses.add(responses.GET, SOURCE_URL, status=503)
    adapter = StreamMarineAdapter("pst", SOURCE_URL)
    result = adapter.fetch(PROVIDER)
    assert result == []
