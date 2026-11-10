"""Redact sensitive information from structured event records."""


SENSITIVE = {"token", "password", "secret", "authorization", "api_key"}


def redact_record(value):
    if isinstance(value, dict):
        return {
            key: "***" if key.lower() in SENSITIVE else redact_record(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_record(item) for item in value]
    return value
