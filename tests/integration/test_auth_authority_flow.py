import json
import subprocess
from uuid import uuid4

from conftest import AUTH_URL, AUTHORITY_URL, request_json, wait_for


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
        event["event_type"] == "authority.granted" and event["grantee_id"] == user_id
        for event in events
    )
