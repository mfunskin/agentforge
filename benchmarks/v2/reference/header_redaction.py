"""Redact sensitive HTTP headers before logging."""

SENSITIVE = {"authorization", "proxy-authorization", "x-api-key", "cookie", "set-cookie"}


def redact_headers(headers):
    return {
        key: "***" if key.lower() in SENSITIVE else value
        for key, value in headers.items()
    }
