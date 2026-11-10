from src.rate_limiter import TokenBucket


def test_uses_entire_capacity():
    clock = lambda: 0
    bucket = TokenBucket(2, 1, clock)
    assert bucket.allow()
    assert bucket.allow()
    assert not bucket.allow()


def test_full_refill_after_elapsed_time():
    time = [0.0]
    bucket = TokenBucket(2, 1, lambda: time[0])
    assert bucket.allow(2)
    time[0] = 2.0
    assert bucket.allow(2)


def test_insufficient_tokens_are_rejected():
    bucket = TokenBucket(3, 0, lambda: 0)
    assert bucket.allow(2)
    assert not bucket.allow(2)
