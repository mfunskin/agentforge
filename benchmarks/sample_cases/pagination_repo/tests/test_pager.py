import pytest

from src.pager import collect_pages


def test_single_page_included():
    assert collect_pages(lambda cursor: ([1, 2], None)) == [1, 2]


def test_three_pages():
    pages = {
        None: (["a"], "next"),
        "next": (["b"], "last"),
        "last": (["c"], None),
    }
    assert collect_pages(lambda cursor: pages[cursor]) == ["a", "b", "c"]


def test_empty_intermediate_page():
    pages = {
        None: ([1], "second"),
        "second": ([], "third"),
        "third": ([3], None),
    }
    assert collect_pages(lambda cursor: pages[cursor]) == [1, 3]


def test_empty_first_page():
    assert collect_pages(lambda cursor: ([], None)) == []


def test_repeated_cursor_raises():
    pages = {
        None: ([1], "next"),
        "next": ([2], "next"),
    }
    with pytest.raises(ValueError, match="cursor"):
        collect_pages(lambda cursor: pages[cursor])
