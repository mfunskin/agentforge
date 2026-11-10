"""Resume an event consumer from a stored offset."""


def process_events(events, checkpoint, handle, save):
    for event in events:
        offset = event["offset"]
        if offset <= checkpoint:
            continue
        handle(event)
        save(offset)
        checkpoint = offset
    return checkpoint
