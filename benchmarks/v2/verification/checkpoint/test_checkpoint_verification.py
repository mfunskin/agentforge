import pytest

from src.checkpoint import process_events


def test_persistence_happens_after_handler():
    events = []
    def handle(event):
        events.append(("handle", event["offset"]))
    def save(offset):
        events.append(("save", offset))
    assert process_events([{"offset": 2}], 1, handle, save) == 2
    assert events == [("handle", 2), ("save", 2)]


def test_handler_failure_does_not_save_failed_offset():
    saved = []
    def handle(event):
        if event["offset"] == 3:
            raise RuntimeError("handler failed")
    with pytest.raises(RuntimeError, match="handler failed"):
        process_events(
            [{"offset": 2}, {"offset": 3}], 1, handle, saved.append,
        )
    assert saved == [2]


def test_out_of_order_old_offset_is_skipped():
    handled = []
    result = process_events(
        [{"offset": 4}, {"offset": 2}, {"offset": 5}], 1,
        lambda event: handled.append(event["offset"]), lambda offset: None,
    )
    assert result == 5
    assert handled == [4, 5]
