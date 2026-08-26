from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Task
from app.service import mark_overdue_tasks


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
    client, sessions, users, _, events = case_context
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
    assert transitioned.json()["wait_state"]["stages_known"] is True
    assert transitioned.json()["wait_state"]["current_stage"] == "submitted"
    assert [event[1]["event_type"] for event in events.events].count("task.created") == 4
    assert events.events[-1][1]["event_type"] == "task.status_changed"

    advanced = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/stage",
        headers=headers(user_id),
        json={"stage": "under_review"},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["wait_state"]["current_stage"] == "under_review"
    assert events.events[-1][1]["event_type"] == "task.stage_advanced"

    async with sessions() as session:
        task = await session.scalar(
            select(Task).where(Task.id == UUID(task_id)).options(selectinload(Task.wait_state))
        )
        task.wait_state.submitted_at = datetime.now(UTC) - timedelta(days=10)
        task.wait_state.estimated_wait_days_max = 1
        await session.commit()
        assert await mark_overdue_tasks(session) == 1

    overdue = await client.get(f"/api/cases/{case_id}/tasks/{task_id}", headers=headers(user_id))
    assert overdue.json()["wait_state"]["is_overdue"] is True

    completed = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/transition",
        headers=headers(user_id),
        json={
            "status": "completed",
            "output_data": {"produced_documents": ["death_certificate"]},
        },
    )
    assert completed.status_code == 200
    topic, event = events.events[-1]
    assert topic == "tasks"
    assert event["event_type"] == "task.completed"
    assert event["owner_user_id"] == str(user_id)
    assert event["task_type"]
    assert event["output_data"] == {"produced_documents": ["death_certificate"]}


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


@pytest.mark.asyncio
async def test_failed_task_uses_ai_rejection_interpretation(case_context) -> None:
    client, _, users, _, events = case_context
    user_id = uuid4()
    users.add(user_id)
    created = await client.post("/api/cases", headers=headers(user_id), json=payload())
    task_id = created.json()["tasks_by_group"]["ready"][0]["task_id"]
    submitted = await client.post(
        f"/api/cases/{created.json()['case_id']}/tasks/{task_id}/transition",
        headers=headers(user_id),
        json={"status": "submitted"},
    )
    assert submitted.status_code == 200

    failed = await client.post(
        f"/api/cases/{created.json()['case_id']}/tasks/{task_id}/transition",
        headers=headers(user_id),
        json={
            "status": "failed",
            "output_data": {"rejection_text": "Legal heir certificate required"},
        },
    )
    assert failed.status_code == 200
    assert events.events[-1][1]["output_data"]["rejection_interpretation"]["remediation_steps"] == [
        "add_task:legal_heir_certificate:bescom_transfer"
    ]


@pytest.mark.asyncio
async def test_task_review_creates_approval_and_submission_receipt(case_context) -> None:
    client, _, users, _, _ = case_context
    user_id = uuid4()
    users.add(user_id)
    created = await client.post("/api/cases", headers=headers(user_id), json=payload())
    case_id = created.json()["case_id"]
    task_id = created.json()["tasks_by_group"]["ready"][0]["task_id"]

    updated = await client.patch(
        f"/api/cases/{case_id}/tasks/{task_id}/detail",
        headers=headers(user_id),
        json={"input_data": {"deceased_name": "Rajesh Kumar"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["input_data"]["deceased_name"] == "Rajesh Kumar"

    prepared = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/prepare",
        headers=headers(user_id),
    )
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()["status"] == "pending"

    approved = await client.post(
        f"/api/approvals/{prepared.json()['id']}/approve",
        headers=headers(user_id),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "submitted"
    assert approved.json()["external_reference_id"].startswith("CB/DEATH_CERTIFICATE/")

    case = await client.get(f"/api/cases/{case_id}", headers=headers(user_id))
    assert case.json()["tasks_by_group"]["waiting"][0]["task_id"] == task_id

    withdrawable = await client.get("/api/cases/withdrawable", headers=headers(user_id))
    assert withdrawable.json()["withdrawable"][0]["can_withdraw"] is True
    withdrawn = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/withdraw", headers=headers(user_id)
    )
    assert withdrawn.json()["task_status"] == "cancelled"
    repeated = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/withdraw", headers=headers(user_id)
    )
    assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_case_can_be_created_for_a_family_member(case_context) -> None:
    client, _, users, _, events = case_context
    user_id = uuid4()
    users.add(user_id)
    case_payload = payload()
    case_payload["subject_person_index"] = 0
    case_payload["subject_relationship"] = "father"

    created = await client.post("/api/cases", headers=headers(user_id), json=case_payload)
    assert created.status_code == 201, created.text
    assert created.json()["my_role"] == "coordinator"
    assert created.json()["subject"]["name"] == "Rajesh Kumar"
    assert created.json()["limitations"]

    context = await client.get("/api/cases/context/for-whom", headers=headers(user_id))
    assert context.status_code == 200
    family = next(option for option in context.json()["options"] if option["type"] == "family")
    assert family["members"][0]["relationship"] == "father"
    assert any(event[1]["event_type"] == "case.created" for event in events.events)

    case_id = created.json()["case_id"]
    task_id = created.json()["tasks_by_group"]["ready"][0]["task_id"]
    for next_status in ("in_progress", "awaiting_approval"):
        transitioned = await client.post(
            f"/api/cases/{case_id}/tasks/{task_id}/transition",
            headers=headers(user_id),
            json={"status": next_status},
        )
        assert transitioned.status_code == 200, transitioned.text
    forbidden = await client.post(
        f"/api/cases/{case_id}/tasks/{task_id}/transition",
        headers=headers(user_id),
        json={"status": "submitted"},
    )
    assert forbidden.status_code == 403
    assert "As coordinator" in forbidden.json()["detail"]
