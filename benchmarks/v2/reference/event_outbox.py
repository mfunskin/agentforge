"""Prepare an idempotent event outbox."""


def enqueue_events(existing, incoming):
    result = []
    seen = set()
    for event in [*existing, *incoming]:
        if not isinstance(event, dict) or not isinstance(event.get("id"), str):
            raise ValueError("event id must be a string")
        if not event["id"]:
            raise ValueError("event id must not be empty")
        if event["id"] not in seen:
            result.append(event.copy())
            seen.add(event["id"])
    return result
