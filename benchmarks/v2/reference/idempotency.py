"""Execute idempotent requests using a caller-owned cache."""

import hashlib
import json


def process_once(key, payload, store, handler):
    if not isinstance(key, str) or not key.strip():
        raise ValueError("idempotency key must be a nonempty string")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    if key in store:
        original_fingerprint, result = store[key]
        if fingerprint != original_fingerprint:
            raise ValueError("idempotency key reused with different payload")
        return result
    result = handler(payload)
    store[key] = (fingerprint, result)
    return result
