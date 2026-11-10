import pytest

from src.utf8_batches import batch_records


def test_utf8_multibyte_sizes_are_counted():
    assert batch_records(["é", "a", "b"], 3) == [["é", "a"], ["b"]]


def test_exact_byte_limit_can_be_used():
    assert batch_records(["ab", "cd", "e"], 4) == [["ab", "cd"], ["e"]]


def test_oversized_record_is_rejected():
    with pytest.raises(ValueError, match="record"):
        batch_records(["abcdef"], 3)
