"""Evaluate role permissions for service actions."""


def can_access(role, action):
    if role == "admin":
        return True
    return action in {"read", "write"}
