import pytest

from src.utf8_batches import batch_records


def test_empty_input_produces_no_empty_batch():
    assert batch_records([], 2) == []


def test_generator_consumed_once_with_stable_order():
    def records():
        yield "a"
        yield "bb"
        yield "c"
        yield "é"
    assert batch_records(records(), 3) == [["a", "bb"], ["c", "é"]]


def test_invalid_budgets():
    for size in (0, -1, True):
        with pytest.raises(ValueError, match="max_bytes"):
            batch_records(["a"], size)


def test_invalid_records_rejected():
    with pytest.raises(TypeError):
        batch_records(["a", 3], 5)


def test_single_record_exact_limit():
    assert batch_records(["é"], 2) == [["é"]]
