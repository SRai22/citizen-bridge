import json
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from uuid import uuid4

from conftest import FRONTEND_URL, GATEWAY_URL


def test_walking_skeleton_repeats_three_times_under_thirty_seconds() -> None:
    started_at = time.monotonic()
    assert urllib.request.urlopen(f"{GATEWAY_URL}/api/legacy/health", timeout=5).status == 200

    for _ in range(3):
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        username = f"walk-{uuid4().hex[:10]}"
        password = "walking-skeleton-password"

        status, _ = request_json(
            client,
            "POST",
            "/api/auth/register",
            {
                "username": username,
                "password": password,
                "name": "Walking Skeleton User",
                "date_of_birth": "1990-01-01",
                "city": "Bengaluru",
                "state": "Karnataka",
            },
        )
        assert status == 201
        assert request_json(
            client,
            "POST",
            "/api/auth/login",
            {"username": username, "password": password},
        )[0] == 200

        status, catalog = request_json(client, "GET", "/api/catalog/categories")
        assert status == 200
        assert catalog["categories"][0]["title"] == "Someone Passed Away"

        status, intake = request_json(client, "POST", "/api/intake/start")
        assert status == 200
        session_id = intake["session_id"]
        for answer in (
            "My father passed away",
            "His name was Rajesh Kumar",
            "Yes, my mother survives him",
            "Bengaluru, Karnataka; BESCOM and ration card",
        ):
            status, intake = request_json(
                client,
                "POST",
                f"/api/intake/{session_id}/message",
                {"message": answer},
            )
            assert status == 200
        assert intake["status"] == "complete"

        status, created = request_json(client, "POST", f"/api/intake/{session_id}/confirm")
        assert status == 201
        status, case = request_json(client, "GET", f"/api/cases/{created['case_id']}")
        assert status == 200
        assert case["my_role"] == "owner"
        assert case["progress"] == {"completed": 0, "total": 4}
        assert sum(len(tasks) for tasks in case["tasks_by_group"].values()) == 4
        assert client.open(f"{FRONTEND_URL}/case/{created['case_id']}", timeout=10).status == 200

    assert time.monotonic() - started_at < 30


def request_json(
    client: urllib.request.OpenerDirector,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(
        f"{FRONTEND_URL}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with client.open(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)
