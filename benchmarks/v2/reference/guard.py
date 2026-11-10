"""Reject requests that are not authorized for an action."""

from src.policy import can_access


def require_permission(user, action):
    role = user.get("role") if isinstance(user, dict) else None
    if not can_access(role, action):
        raise PermissionError("permission denied")
    return True
