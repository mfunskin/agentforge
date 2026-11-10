"""Small HTTP retry helper with an injected transport and sleeper."""


def fetch_with_retry(send, sleep, attempts=3):
    response = send()
    if response["status"] >= 500:
        sleep(1)
        return send()
    return response
