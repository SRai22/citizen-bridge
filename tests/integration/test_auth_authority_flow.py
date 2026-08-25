import json
import subprocess
from uuid import uuid4

from conftest import AUTH_URL, AUTHORITY_URL, CASE_URL, request_json, wait_for


def test_registration_creates_default_authority_and_kafka_event() -> None:
    username = f"integration-{uuid4().hex[:10]}"
    status, registration = request_json(
        "POST",
        f"{AUTH_URL}/api/auth/register",
        {
            "username": username,
            "password": "integration-password",
            "name": "Integration User",
            "date_of_birth": "1990-01-01",
            "city": "Bengaluru",
        },
    )
    assert status == 201
    user_id = str(registration["user_id"])
    headers = {"Authorization": f"Bearer {registration['access_token']}"}

    result: dict[str, object] = {}

    def default_grant_exists() -> bool:
        nonlocal result
        check_status, result = request_json(
            "GET",
            f"{AUTHORITY_URL}/api/authority/check"
            f"?user_id={user_id}&resource_type=person&resource_id={user_id}&action=manage",
            headers=headers,
        )
        return check_status == 200 and result.get("allowed") is True

    wait_for(default_grant_exists)
    assert result["role"] == "owner"

    consumed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.test.yml",
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-consumer.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "authority",
            "--from-beginning",
            "--max-messages",
            "1",
            "--timeout-ms",
            "10000",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    events = [
        json.loads(line)
        for line in consumed.stdout.splitlines()
        if line.startswith("{")
    ]
    assert any(
        event["event_type"] == "authority.granted"
        and event["payload"]["grantee_id"] == user_id
        for event in events
    )

    case_status, created_case = request_json(
        "POST",
        f"{CASE_URL}/api/cases",
        {
            "life_event": {
                "type": "father_death",
                "context": {
                    "deceased": {
                        "is_deceased": True,
                        "pension_status": "active",
                        "was_electricity_account_holder": True,
                        "was_head_of_household": True,
                    },
                    "surviving_spouse": {"exists": True},
                    "location": {"state": "Karnataka"},
                    "assets": {"bescom": True, "ration_card": True},
                },
            },
            "household_profile": {
                "location_city": "Bengaluru",
                "location_state": "Karnataka",
                "people": [
                    {
                        "name": "Rajesh Kumar",
                        "relationship": "father",
                        "is_deceased": True,
                    }
                ],
            },
        },
        headers,
    )
    assert case_status == 201
    assert created_case["my_role"] == "owner"
    assert created_case["progress"] == {"completed": 0, "total": 4}
    assert len(created_case["tasks_by_group"]["ready"]) == 1

    list_status, listed = request_json("GET", f"{CASE_URL}/api/cases", headers=headers)
    assert list_status == 200
    assert listed["cases"][0]["case_id"] == created_case["case_id"]

    case_events = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.test.yml",
            "exec",
            "-T",
            "kafka",
            "/opt/kafka/bin/kafka-console-consumer.sh",
            "--bootstrap-server",
            "kafka:9092",
            "--topic",
            "cases",
            "--from-beginning",
            "--max-messages",
            "1",
            "--timeout-ms",
            "10000",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert any(
        event.get("event_type") == "case.created"
        and event.get("payload", {}).get("case_id") == created_case["case_id"]
        for event in (
            json.loads(line)
            for line in case_events.stdout.splitlines()
            if line.startswith("{")
        )
    )
