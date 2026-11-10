import pytest

from src.guard import require_permission
from src.policy import can_access


def test_reader_cannot_write():
    assert not can_access("reader", "write")
    with pytest.raises(PermissionError, match="permission"):
        require_permission({"role": "reader"}, "write")


def test_admin_can_delete():
    assert require_permission({"role": "admin"}, "delete") is True


def test_writer_can_read_and_write():
    assert can_access("writer", "read")
    assert require_permission({"role": "writer"}, "write") is True


def test_unknown_role_denied():
    with pytest.raises(PermissionError, match="permission"):
        require_permission({"role": "visitor"}, "read")
