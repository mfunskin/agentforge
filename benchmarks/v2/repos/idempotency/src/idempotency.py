"""Execute idempotent requests using a caller-owned cache."""


def process_once(key, payload, store, handler):
    if key in store:
        return store[key]
    result = handler(payload)
    store[key] = result
    return result
