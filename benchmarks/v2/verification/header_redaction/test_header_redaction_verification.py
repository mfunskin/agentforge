from src.header_redaction import redact_headers


def test_cookie_and_proxy_authorization_redacted():
    result = redact_headers({
        "cooKIE": "session=abc",
        "Proxy-Authorization": "Basic secret",
        "Set-Cookie": "session=def",
    })
    assert all(value == "***" for value in result.values())


def test_api_key_mixed_case():
    assert redact_headers({"x-Api-kEy": "secret"}) == {"x-Api-kEy": "***"}


def test_input_mapping_is_unchanged():
    original = {"authorization": "sensitive", "X-Trace": "fine"}
    result = redact_headers(original)
    assert original["authorization"] == "sensitive"
    result["X-Trace"] = "changed"
    assert original["X-Trace"] == "fine"
