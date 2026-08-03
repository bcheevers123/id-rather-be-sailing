from pipeline.freshness import compute_freshness


def test_verified_within_24h():
    assert compute_freshness("2026-08-03T06:00:00Z", "2026-08-03T12:00:00Z") == "verified"


def test_recently_checked_within_7_days():
    assert compute_freshness("2026-07-28T06:00:00Z", "2026-08-03T06:00:00Z") == "recently_checked"


def test_stale_over_7_days():
    assert compute_freshness("2026-07-25T06:00:00Z", "2026-08-03T06:00:00Z") == "stale"


def test_none_last_verified_returns_stale():
    assert compute_freshness(None, "2026-08-03T06:00:00Z") == "stale"
