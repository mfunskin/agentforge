import pytest

from src.env_values import parse_env


def test_empty_value_is_allowed():
    assert parse_env(["EMPTY="]) == {"EMPTY": ""}


def test_unquoted_whitespace_trimmed():
    assert parse_env(["  MODE =   active  "]) == {"MODE": "active"}


def test_hash_inside_value_is_not_a_comment():
    assert parse_env(["COLOR=blue#4"]) == {"COLOR": "blue#4"}


def test_invalid_variable_names():
    for text in ("1NAME=value", "=missing", "A-B=value"):
        with pytest.raises(ValueError, match="variable"):
            parse_env([text])


def test_unclosed_quotation_rejected():
    with pytest.raises(ValueError, match="quoted"):
        parse_env(['NAME="unfinished'])
