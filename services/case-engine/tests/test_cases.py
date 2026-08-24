from uuid import uuid4

import pytest


def headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


def payload() -> dict[str, object]:
    return {
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
    }


@pytest.mark.asyncio
async def test_authenticated_case_flow(case_context) -> None:
    client, _, users, _, events = case_context
    user_id, outsider_id = uuid4(), uuid4()
    users.update({user_id, outsider_id})

    assert (await client.get("/api/cases")).status_code == 401
    created = await client.post("/api/cases", headers=headers(user_id), json=payload())
    assert created.status_code == 201, created.text
    body = created.json()
    case_id = body["case_id"]
    assert body["my_role"] == "owner"
    assert body["progress"] == {"completed": 0, "total": 4}
    assert len(body["tasks_by_group"]["ready"]) == 1
    assert len(body["tasks_by_group"]["blocked"]) == 3

    listed = await client.get("/api/cases?status=active", headers=headers(user_id))
    assert listed.status_code == 200
    assert listed.json()["cases"][0]["case_id"] == case_id
    forbidden = await client.get(f"/api/cases/{case_id}", headers=headers(outsider_id))
    assert forbidden.status_code == 403

    task_id = body["tasks_by_group"]["ready"][0]["task_id"]
    transitioned = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/transition",
        headers=headers(user_id),
        json={"status": "submitted"},
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["wait_state"]["status_label"] == "Processing"
    assert [event[1]["event_type"] for event in events.events].count("task.created") == 4
    assert events.events[-1][1]["event_type"] == "task.status_changed"


@pytest.mark.asyncio
async def test_rejects_inconsistent_workflow_profile(case_context) -> None:
    client, _, users, _, _ = case_context
    user_id = uuid4()
    users.add(user_id)
    invalid = payload()
    invalid["life_event"]["context"]["location"]["state"] = "Tamil Nadu"
    response = await client.post("/api/cases", headers=headers(user_id), json=invalid)
    assert response.status_code == 422
    assert "requires inactive workflow" in response.json()["detail"]
