import pytest

from src.retry_policy import fetch_with_retry


def test_retry_budget_is_honored():
    calls, delays = [], []
    result = fetch_with_retry(
        lambda: calls.append(1) or {"status": 500},
        delays.append, attempts=4,
    )
    assert result["status"] == 500
    assert len(calls) == 4
    assert delays == [1.0, 1.0, 1.0]


def test_case_insensitive_header_and_malformed_delay():
    replies = iter([
        {"status": 429, "headers": {"retry-after": "bad"}},
        {"status": 200},
    ])
    delays = []
    fetch_with_retry(lambda: next(replies), delays.append)
    assert delays == [1.0]


def test_invalid_retry_budget():
    with pytest.raises(ValueError, match="attempts"):
        fetch_with_retry(lambda: {"status": 200}, lambda delay: None, attempts=0)
