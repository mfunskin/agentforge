"""Resume an event consumer from a stored offset."""


def process_events(events, checkpoint, handle, save):
    for event in events:
        if event["offset"] >= checkpoint:
            save(event["offset"])
            handle(event)
            checkpoint = event["offset"]
    return checkpoint
