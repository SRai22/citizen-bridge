from uuid import uuid4

from conftest import (
    AUTH_URL,
    CASE_URL,
    DOCUMENT_URL,
    NOTIFICATION_URL,
    request_json,
    wait_for,
)


def test_task_completion_creates_document_and_notifications() -> None:
    status, registration = request_json(
        "POST",
        f"{AUTH_URL}/api/auth/register",
        {
            "username": f"step9-{uuid4().hex[:10]}",
            "password": "step9-integration-password",
            "name": "Step Nine User",
            "date_of_birth": "1990-01-01",
            "city": "Bengaluru",
        },
    )
    assert status == 201
    headers = {"Authorization": f"Bearer {registration['access_token']}"}

    status, case = request_json(
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
            }
        },
        headers,
    )
    assert status == 201
    case_id = case["case_id"]
    task_id = case["tasks_by_group"]["ready"][0]["task_id"]

    assert request_json(
        "POST",
        f"{CASE_URL}/api/cases/{case_id}/tasks/{task_id}/transition",
        {"status": "submitted"},
        headers,
    )[0] == 200
    assert request_json(
        "POST",
        f"{CASE_URL}/api/cases/{case_id}/tasks/{task_id}/transition",
        {"status": "completed"},
        headers,
    )[0] == 200

    documents: dict[str, object] = {}

    def document_arrived() -> bool:
        nonlocal documents
        doc_status, documents = request_json(
            "GET", f"{DOCUMENT_URL}/api/docs", headers=headers
        )
        return doc_status == 200 and bool(
            documents.get("documents_by_category", {}).get("certificates")
        )

    wait_for(document_arrived)
    document = documents["documents_by_category"]["certificates"][0]
    assert document["provenance_type"] == "platform_issued"
    assert document["source_task_id"] == task_id

    notifications: dict[str, object] = {}

    def notifications_arrived() -> bool:
        nonlocal notifications
        notification_status, notifications = request_json(
            "GET", f"{NOTIFICATION_URL}/api/notifications", headers=headers
        )
        return notification_status == 200 and len(notifications.get("notifications", [])) >= 2

    wait_for(notifications_arrived)
    kinds = {item["notification_type"] for item in notifications["notifications"]}
    assert {"task_status", "document_issued"} <= kinds
