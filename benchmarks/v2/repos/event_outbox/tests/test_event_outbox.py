from src.event_outbox import enqueue_events


def test_deduplicate_incoming_batch():
    result = enqueue_events([], [{"id": "a"}, {"id": "a"}, {"id": "b"}])
    assert [event["id"] for event in result] == ["a", "b"]


def test_preserve_existing_order():
    result = enqueue_events(
        [{"id": "x"}, {"id": "y"}], [{"id": "x"}, {"id": "z"}],
    )
    assert [event["id"] for event in result] == ["x", "y", "z"]


def test_new_ids_keep_arrival_order():
    result = enqueue_events([], [{"id": "b"}, {"id": "a"}])
    assert [event["id"] for event in result] == ["b", "a"]
