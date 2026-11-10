"""Group text records into bounded delivery batches."""


def batch_records(records, max_bytes):
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    batches = []
    current = []
    used = 0
    for record in records:
        if not isinstance(record, str):
            raise TypeError("records must be strings")
        size = len(record.encode("utf-8"))
        if size > max_bytes:
            raise ValueError("record exceeds max_bytes")
        if current and used + size > max_bytes:
            batches.append(current)
            current = []
            used = 0
        current.append(record)
        used += size
    if current:
        batches.append(current)
    return batches
