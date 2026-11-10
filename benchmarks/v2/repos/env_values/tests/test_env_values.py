import pytest

from src.env_values import parse_env


def test_equals_sign_is_part_of_value():
    assert parse_env(["URL=https://example.test/?a=1"]) == {
        "URL": "https://example.test/?a=1",
    }


def test_comments_blank_lines_and_duplicates():
    assert parse_env([" # ignored", "", "MODE=dev", "MODE=prod"]) == {
        "MODE": "prod",
    }


def test_quoted_value_preserves_inner_whitespace():
    assert parse_env([' LABEL = "  a b  " ']) == {"LABEL": "  a b  "}


def test_missing_separator_rejected():
    with pytest.raises(ValueError):
        parse_env(["BROKEN"])
