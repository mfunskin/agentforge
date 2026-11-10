import pytest

from src.idempotency import process_once


def test_identical_request_executes_once():
    calls = []
    store = {}
    handler = lambda payload: calls.append(payload) or {"ok": True}
    assert process_once("request-1", {"a": 1}, store, handler) == {"ok": True}
    assert process_once("request-1", {"a": 1}, store, handler) == {"ok": True}
    assert len(calls) == 1


def test_different_payload_cannot_reuse_key():
    store = {}
    process_once("same", {"count": 1}, store, lambda payload: 10)
    with pytest.raises(ValueError, match="payload"):
        process_once("same", {"count": 2}, store, lambda payload: 11)


def test_dictionary_key_order_is_irrelevant():
    store = {}
    process_once("sorted", {"a": 1, "b": 2}, store, lambda payload: "done")
    assert process_once("sorted", {"b": 2, "a": 1}, store, lambda p: "wrong") == "done"
