"""Serialize structured audit events for stable log records."""

from src.redaction import redact_record


def format_audit_event(event):
    return str(redact_record(event))
