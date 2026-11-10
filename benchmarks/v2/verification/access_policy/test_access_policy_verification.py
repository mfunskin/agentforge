import pytest

from src.guard import require_permission
from src.policy import can_access


def test_admin_not_allowed_unknown_actions():
    assert can_access("admin", "reset-system") is False
    with pytest.raises(PermissionError):
        require_permission({"role": "admin"}, "reset-system")


def test_writer_cannot_delete():
    with pytest.raises(PermissionError):
        require_permission({"role": "writer"}, "delete")


def test_missing_role_and_user_denied():
    for user in ({}, None, {"role": None}):
        with pytest.raises(PermissionError, match="permission"):
            require_permission(user, "read")


def test_reader_can_read():
    assert require_permission({"role": "reader"}, "read") is True


def test_unauthorized_guard_never_returns_false():
    with pytest.raises(PermissionError):
        require_permission({"role": "reader"}, "delete")
