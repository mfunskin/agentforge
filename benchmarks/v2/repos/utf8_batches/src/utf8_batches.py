"""Group text records into bounded delivery batches."""


def batch_records(records, max_bytes):
    batches = []
    current = []
    used = 0
    for record in records:
        if used + len(record) > max_bytes:
            batches.append(current)
            current = []
            used = 0
        current.append(record)
        used += len(record)
    if current:
        batches.append(current)
    return batches
