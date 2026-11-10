from src.parser import parse_record


def test_plain_fields():
    assert parse_record("red,blue,green") == ["red", "blue", "green"]


def test_quoted_comma():
    assert parse_record('"red, blue",green') == ["red, blue", "green"]


def test_doubled_quotes():
    assert parse_record('"She said ""hello""",done') == ['She said "hello"', "done"]


def test_empty_fields():
    assert parse_record("first,,last,") == ["first", "", "last", ""]


def test_preserves_quoted_whitespace():
    assert parse_record('" leading ",plain') == [" leading ", "plain"]
