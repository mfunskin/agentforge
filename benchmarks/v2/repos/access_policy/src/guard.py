"""Reject requests that are not authorized for an action."""

from src.policy import can_access


def require_permission(user, action):
    return can_access(user.get("role"), action)
