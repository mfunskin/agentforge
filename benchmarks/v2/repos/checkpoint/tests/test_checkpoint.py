from src.checkpoint import process_events


def test_skips_replayed_checkpoint():
    handled = []
    saved = []
    result = process_events(
        [{"offset": 5}, {"offset": 6}, {"offset": 7}], 5,
        lambda event: handled.append(event["offset"]), saved.append,
    )
    assert result == 7
    assert handled == [6, 7]
    assert saved == [6, 7]


def test_empty_batch_retains_checkpoint():
    assert process_events([], 9, lambda event: None, lambda offset: None) == 9


def test_duplicate_offsets_only_handled_once():
    handled = []
    process_events(
        [{"offset": 1}, {"offset": 1}, {"offset": 2}], 0,
        lambda event: handled.append(event["offset"]), lambda offset: None,
    )
    assert handled == [1, 2]
