import requests


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    """Records requests and replies with queued responses or exceptions."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        return response


OPEN_ER_PAYLOAD = {
    "result": "success",
    "base_code": "USD",
    "time_last_update_unix": 1794441751,
    "rates": {"USD": 1, "COP": 4000, "EUR": 0.9, "MXN": 18.5, "BAD": "x"},
}
