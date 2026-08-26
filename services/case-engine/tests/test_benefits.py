from uuid import uuid4

import pytest

from app.benefits import discover


def headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


@pytest.mark.asyncio
async def test_benefit_readiness_apply_and_activation(case_context) -> None:
    client, _, users, _, events = case_context
    user_id = uuid4()
    users.add(user_id)

    eligible = await client.get("/api/cases/benefits/eligible", headers=headers(user_id))
    assert eligible.status_code == 200, eligible.text
    widow = next(item for item in eligible.json()["benefits"] if item["id"] == "widow_pension")
    assert widow["eligibility"]["status"] == "eligible"
    assert widow["readiness"]["percentage"] == 100
    assert widow["eligibility"]["rule_results"][2]["source"]["type"] == "user_input"

    applied = await client.post("/api/cases/benefits/widow_pension/apply", headers=headers(user_id))
    assert applied.status_code == 201, applied.text
    case = applied.json()["case"]
    task_id = case["tasks_by_group"]["ready"][0]["task_id"]
    for next_status in ("submitted", "completed"):
        transitioned = await client.post(
            f"/api/cases/{case['case_id']}/tasks/{task_id}/transition",
            headers=headers(user_id),
            json={"status": next_status},
        )
        assert transitioned.status_code == 200, transitioned.text

    active = await client.get("/api/cases/benefits/active", headers=headers(user_id))
    assert active.json()["benefits"][0]["benefit_id"] == "widow_pension"
    assert any(event[1]["event_type"] == "case.completed" for event in events.events)


@pytest.mark.asyncio
async def test_unknown_benefit_is_not_applied(case_context) -> None:
    client, _, users, _, _ = case_context
    user_id = uuid4()
    users.add(user_id)
    response = await client.post("/api/cases/benefits/missing/apply", headers=headers(user_id))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_profile_update_publishes_a_new_discovery_only_once(case_context) -> None:
    _, sessions, _, _, events = case_context
    user_id = uuid4()
    benefit = {
        "id": "income_support",
        "name": "Income Support",
        "amount": "₹500 per month",
        "eligibility_rules": [{"field": "annual_income", "operator": "lt", "value": 200000}],
        "required_documents": [],
    }

    class Auth:
        async def profile_by_user(self, requested_user_id: str) -> dict:
            assert requested_user_id == str(user_id)
            return {"profile": {"annual_income": 120000}}

    class Catalog:
        async def benefits(self) -> list[dict]:
            return [benefit]

    class Documents:
        async def check_requirements(self, requested_user_id: str, types: list[str]) -> dict:
            return {"available": [], "missing": []}

    event = {"user_id": str(user_id), "changed_fields": ["annual_income"]}
    async with sessions() as session:
        await discover(session, events, Auth(), Catalog(), Documents(), event)
        await discover(session, events, Auth(), Catalog(), Documents(), event)

    discoveries = [item for item in events.events if item[1]["event_type"] == "benefit.discovered"]
    assert len(discoveries) == 1
