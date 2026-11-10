"""Serialize structured audit events for stable log records."""

import json

from src.redaction import redact_record


def format_audit_event(event):
    return json.dumps(redact_record(event), sort_keys=True, separators=(",", ":"))
