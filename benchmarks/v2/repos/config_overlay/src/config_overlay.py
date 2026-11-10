"""Combine service configuration with deployment overrides."""


def merge_config(defaults, overrides):
    merged = dict(defaults)
    merged.update(overrides)
    return merged
