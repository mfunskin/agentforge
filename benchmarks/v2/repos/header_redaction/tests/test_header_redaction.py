from src.header_redaction import redact_headers


def test_authorization_is_masked():
    result = redact_headers({"Authorization": "Bearer secret"})
    assert result == {"Authorization": "***"}


def test_lowercase_authorization_is_masked():
    result = redact_headers({"authorization": "Bearer token"})
    assert result == {"authorization": "***"}


def test_non_sensitive_values_are_preserved():
    headers = {"Content-Type": "application/json", "X-Trace": "abc"}
    assert redact_headers(headers) == headers
