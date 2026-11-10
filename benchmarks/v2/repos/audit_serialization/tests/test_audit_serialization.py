import json

from src.audit_log import format_audit_event
from src.redaction import redact_record


def test_nested_sensitive_values_are_masked():
    source = {"actor": "sam", "context": {"Authorization": "Bearer private"}}
    assert redact_record(source) == {
        "actor": "sam", "context": {"Authorization": "***"},
    }


def test_event_is_valid_json_and_redacted():
    value = format_audit_event({"event": "login", "data": {"token": "secret"}})
    assert json.loads(value) == {"event": "login", "data": {"token": "***"}}


def test_json_is_canonical():
    first = format_audit_event({"z": 2, "a": 1})
    second = format_audit_event({"a": 1, "z": 2})
    assert first == second == '{"a":1,"z":2}'
