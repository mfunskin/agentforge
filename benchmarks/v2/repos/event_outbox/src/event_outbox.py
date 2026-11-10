"""Prepare an idempotent event outbox."""


def enqueue_events(existing, incoming):
    seen = {event["id"] for event in existing}
    for event in incoming:
        if event["id"] not in seen:
            existing.append(event)
    return existing
