from datetime import datetime, timedelta, timezone

from src.schedule_next import next_run


ANCHOR = datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
INTERVAL = timedelta(minutes=15)


def test_exact_boundary_moves_to_next_slot():
    assert next_run(ANCHOR, INTERVAL, ANCHOR) == ANCHOR + INTERVAL


def test_many_missed_slots_keep_original_alignment():
    now = ANCHOR + timedelta(minutes=64)
    assert next_run(ANCHOR, INTERVAL, now) == ANCHOR + timedelta(minutes=75)


def test_between_slots_returns_immediately_next():
    now = ANCHOR + timedelta(minutes=16)
    assert next_run(ANCHOR, INTERVAL, now) == ANCHOR + timedelta(minutes=30)
