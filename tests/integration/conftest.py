import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:18001")
AUTHORITY_URL = os.getenv("AUTHORITY_URL", "http://localhost:18002")
CASE_URL = os.getenv("CASE_URL", "http://localhost:18003")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:13000")
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:18080")


def request_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def wait_for(predicate, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise AssertionError("Timed out waiting for integration condition")


@pytest.fixture(scope="session", autouse=True)
def services() -> Iterator[None]:
    for base_url in (AUTH_URL, AUTHORITY_URL, CASE_URL):
        wait_for(lambda url=base_url: request_json("GET", f"{url}/health")[0] == 200)
    wait_for(lambda: request_json("GET", f"{FRONTEND_URL}/api/health")[0] == 200)
    yield
