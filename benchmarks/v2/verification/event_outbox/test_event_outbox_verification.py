import pytest

from src.event_outbox import enqueue_events


def test_caller_collection_is_not_modified():
    existing = [{"id": "old", "value": 1}]
    incoming = [{"id": "new", "value": 2}]
    result = enqueue_events(existing, incoming)
    assert existing == [{"id": "old", "value": 1}]
    result[0]["value"] = 99
    assert existing[0]["value"] == 1
    assert incoming[0]["value"] == 2


def test_missing_id_rejected():
    with pytest.raises(ValueError, match="id"):
        enqueue_events([], [{"data": "no identifier"}])


def test_empty_id_rejected():
    with pytest.raises(ValueError, match="id"):
        enqueue_events([], [{"id": ""}])
