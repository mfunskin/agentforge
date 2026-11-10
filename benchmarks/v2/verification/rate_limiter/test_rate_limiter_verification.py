import pytest

from src.rate_limiter import TokenBucket


def test_backward_clock_does_not_debit_tokens():
    time = [5.0]
    bucket = TokenBucket(1, 1, lambda: time[0])
    assert bucket.allow()
    time[0] = 3.0
    assert not bucket.allow()
    time[0] = 6.0
    assert bucket.allow()


def test_fractional_refill():
    time = [0.0]
    bucket = TokenBucket(1, 0.5, lambda: time[0])
    assert bucket.allow()
    time[0] = 1.0
    assert not bucket.allow()
    time[0] = 2.0
    assert bucket.allow()


def test_invalid_configuration_and_requests():
    with pytest.raises(ValueError):
        TokenBucket(0, 1, lambda: 0)
    with pytest.raises(ValueError):
        TokenBucket(1, -1, lambda: 0)
    bucket = TokenBucket(1, 1, lambda: 0)
    with pytest.raises(ValueError):
        bucket.allow(0)
