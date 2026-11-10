from src.retry_policy import fetch_with_retry


def test_rate_limit_uses_retry_after():
    replies = iter([{"status": 429, "headers": {"Retry-After": "2"}},
                    {"status": 200, "headers": {}}])
    delays = []
    assert fetch_with_retry(lambda: next(replies), delays.append)["status"] == 200
    assert delays == [2.0]


def test_server_error_is_retried():
    replies = iter([{"status": 503}, {"status": 200}])
    assert fetch_with_retry(lambda: next(replies), lambda delay: None)["status"] == 200


def test_client_error_is_not_retried():
    seen = []
    result = fetch_with_retry(lambda: seen.append(1) or {"status": 400}, lambda d: None)
    assert result["status"] == 400
    assert len(seen) == 1
