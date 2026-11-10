"""Redact sensitive information from structured event records."""


SENSITIVE = {"token", "password", "secret", "authorization", "api_key"}


def redact_record(value):
    if isinstance(value, dict):
        return {
            key: "***" if key in SENSITIVE else item
            for key, item in value.items()
        }
    return value
