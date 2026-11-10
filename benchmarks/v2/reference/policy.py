"""Evaluate role permissions for service actions."""


PERMISSIONS = {
    "admin": {"read", "write", "delete"},
    "writer": {"read", "write"},
    "reader": {"read"},
}


def can_access(role, action):
    return action in PERMISSIONS.get(role, set())
