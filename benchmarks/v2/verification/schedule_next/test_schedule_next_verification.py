from datetime import datetime, timedelta, timezone

import pytest

from src.schedule_next import next_run


ANCHOR = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_zero_and_negative_intervals_rejected():
    for duration in (timedelta(0), timedelta(seconds=-1)):
        with pytest.raises(ValueError, match="interval"):
            next_run(ANCHOR, duration, ANCHOR)


def test_now_before_anchor_rejected():
    with pytest.raises(ValueError, match="anchor"):
        next_run(ANCHOR, timedelta(minutes=1), ANCHOR - timedelta(seconds=1))


def test_fractional_intervals_and_exact_slot():
    step = timedelta(milliseconds=500)
    now = ANCHOR + timedelta(seconds=1)
    assert next_run(ANCHOR, step, now) == now + step


def test_utc_aware_schedule_stays_timezone_aware():
    now = ANCHOR + timedelta(days=3, minutes=1)
    result = next_run(ANCHOR, timedelta(days=1), now)
    assert result == ANCHOR + timedelta(days=4)
    assert result.tzinfo == timezone.utc
