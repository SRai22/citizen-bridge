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

        status, intake = request_json(
            client, "POST", "/api/intake/start", {"category_id": "address_change"}
        )
        assert status == 201
        session_id = intake["conversation_id"]
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

        status, confirmed = request_json(
            client,
            "POST",
            f"/api/intake/{session_id}/confirm",
            {"profile_confirmed": True},
        )
        assert status == 200
        profile = confirmed["profile"]
        status, created = request_json(
            client,
            "POST",
            "/api/cases",
            {
                "life_event": {
                    "type": "address_change",
                    "context": {"category_id": "address_change"},
                },
                "household_profile": {
                    "location_city": profile["location"]["city"],
                    "location_state": profile["location"]["state"],
                        "people": [
                            {
                                "name": profile["deceased"]["name"],
                                "relationship": profile["deceased"]["relationship"],
                                "role": None,
                                "is_deceased": False,
                                "attributes": {
                                    "occupation": profile["deceased"]["occupation"],
                                    "pension_status": profile["deceased"]["pension_status"],
                                },
                            },
                            *[
                                {
                                    "name": person["name"],
                                    "relationship": person["relationship"],
                                    "role": None,
                                    "is_deceased": False,
                                    "attributes": {
                                        "occupation": person["occupation"],
                                        "pension_status": person["pension_status"],
                                    },
                                }
                            for person in profile["surviving_members"]
                        ],
                    ],
                },
            },
        )
        assert status == 201
        status, case = request_json(client, "GET", f"/api/cases/{created['case_id']}")
        assert status == 200
        assert case["my_role"] == "owner"
        assert case["progress"] == {"completed": 0, "total": 4}
        assert sum(len(tasks) for tasks in case["tasks_by_group"].values()) == 4
        assert client.open(f"{FRONTEND_URL}/case/{created['case_id']}", timeout=10).status == 200

        task_id = case["tasks_by_group"]["ready"][0]["task_id"]
        status, task = request_json(
            client,
            "PATCH",
            f"/api/cases/{created['case_id']}/tasks/{task_id}",
            {"input_data": {"deceased_name": profile["deceased"]["name"]}},
        )
        assert status == 200
        assert task["input_data"]["deceased_name"] == profile["deceased"]["name"]
        status, approval = request_json(
            client,
            "POST",
            f"/api/cases/{created['case_id']}/tasks/{task_id}/prepare",
        )
        assert status == 200
        assert approval["status"] == "pending"
        assert client.open(
            f"{FRONTEND_URL}/life-events/{created['case_id']}/task/{task_id}/review"
            f"?approval={approval['id']}",
            timeout=10,
        ).status == 200
        status, receipt = request_json(
            client, "POST", f"/api/approvals/{approval['id']}/approve"
        )
        assert status == 200
        assert receipt["status"] == "submitted"
        assert receipt["external_reference_id"].startswith("CB/")

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
