"""Find the next scheduled time for a periodic job."""

from datetime import timedelta


def next_run(anchor, interval, now):
    if not isinstance(interval, timedelta) or interval <= timedelta(0):
        raise ValueError("interval must be positive")
    if now < anchor:
        raise ValueError("now must not precede the anchor")
    elapsed = now - anchor
    steps = elapsed // interval + 1
    return anchor + steps * interval
