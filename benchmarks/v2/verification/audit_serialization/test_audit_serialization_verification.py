import json

from src.audit_log import format_audit_event
from src.redaction import redact_record


def test_list_items_and_mixed_case_keys():
    event = {"messages": [
        {"Password": "abc", "status": 201},
        {"api_key": "key", "Secret": "hidden"},
    ]}
    assert json.loads(format_audit_event(event)) == {
        "messages": [
            {"Password": "***", "status": 201},
            {"api_key": "***", "Secret": "***"},
        ],
    }


def test_recursive_result_does_not_mutate_or_alias_input():
    source = {"nested": [{"status": "ok"}, {"password": "value"}]}
    result = redact_record(source)
    assert source["nested"][1]["password"] == "value"
    result["nested"][0]["status"] = "changed"
    assert source["nested"][0]["status"] == "ok"


def test_serialization_preserves_safe_metadata():
    text = format_audit_event({
        "actor": {"id": 13, "roles": ["reader"]},
        "trace": None,
    })
    assert text == '{"actor":{"id":13,"roles":["reader"]},"trace":null}'
