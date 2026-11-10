"""Small HTTP retry helper with an injected transport and sleeper."""


def fetch_with_retry(send, sleep, attempts=3):
    if not isinstance(attempts, int) or attempts < 1:
        raise ValueError("attempts must be positive")
    for number in range(attempts):
        response = send()
        status = response["status"]
        if status not in {429, 500, 502, 503, 504} or number == attempts - 1:
            return response
        header = response.get("headers", {})
        value = next((v for k, v in header.items() if k.lower() == "retry-after"), None)
        try:
            delay = max(0.0, float(value)) if value is not None else 1.0
        except (TypeError, ValueError):
            delay = 1.0
        sleep(delay)
