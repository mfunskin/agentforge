"""Redact sensitive HTTP headers before logging."""


def redact_headers(headers):
    return {
        key: "***" if key in {"Authorization", "X-API-Key"} else value
        for key, value in headers.items()
    }
