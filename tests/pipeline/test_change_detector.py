from pipeline.change_detector import detect_changes


def test_detects_new_provider():
    previous = {"providers": [{"id": "provider-a", "official_name": "Provider A"}]}
    current = {
        "providers": [
            {"id": "provider-a", "official_name": "Provider A"},
            {"id": "provider-b", "official_name": "Provider B"},
        ]
    }
    changes = detect_changes(previous, current)
    kinds = [c.kind for c in changes]
    assert "provider_added" in kinds


def test_detects_removed_provider():
    previous = {
        "providers": [
            {"id": "provider-a", "official_name": "Provider A"},
            {"id": "provider-b", "official_name": "Provider B"},
        ]
    }
    current = {"providers": [{"id": "provider-a", "official_name": "Provider A"}]}
    changes = detect_changes(previous, current)
    kinds = [c.kind for c in changes]
    assert "provider_removed" in kinds


def test_detects_zero_offerings_anomaly():
    previous = {"offerings_by_provider": {"provider-a": 5}}
    current = {"offerings_by_provider": {"provider-a": 0}}
    changes = detect_changes(previous, current)
    kinds = [c.kind for c in changes]
    assert "zero_offerings_anomaly" in kinds


def test_no_changes_returns_empty():
    state = {"providers": [{"id": "a", "official_name": "A"}], "offerings_by_provider": {"a": 3}}
    changes = detect_changes(state, state)
    assert changes == []
