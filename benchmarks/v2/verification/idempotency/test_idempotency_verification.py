import pytest

from src.idempotency import process_once


def test_failed_handler_is_not_cached():
    store = {}
    def fail(payload):
        raise RuntimeError("backend unavailable")
    with pytest.raises(RuntimeError):
        process_once("retry", {"x": 1}, store, fail)
    assert store == {}
    assert process_once("retry", {"x": 1}, store, lambda payload: "ok") == "ok"


def test_empty_and_invalid_keys():
    for key in ("", "  ", None):
        with pytest.raises(ValueError, match="key"):
            process_once(key, {}, {}, lambda payload: "ok")


def test_payload_is_not_mutated():
    source = {"nested": {"items": [1, 2]}}
    process_once("request", source, {}, lambda payload: len(payload))
    assert source == {"nested": {"items": [1, 2]}}


def test_other_idempotency_key_can_reuse_payload():
    store = {}
    calls = []
    for key in ("first", "second"):
        process_once(key, {"a": 1}, store, lambda p: calls.append(1) or "ok")
    assert len(calls) == 2
