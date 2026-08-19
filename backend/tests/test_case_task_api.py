from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import create_database_engine, get_session, init_db
from app.main import create_app
from app.models import Document, Task, TaskDependency, TaskStatus


@pytest.fixture
async def api_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield client, sessions
    await engine.dispose()


async def create_case(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/cases",
        json={
            "life_event": {
                "type": "parent_death",
                "context": {"source": "guided_intake"},
            },
            "household_profile": {
                "location_city": "Bengaluru",
                "location_state": "Karnataka",
                "people": [
                    {
                        "name": "Arun Rao",
                        "relationship": "father",
                        "is_deceased": True,
                        "attributes": {"pensioner": True},
                    }
                ],
            },
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.anyio
async def test_case_and_task_api_integration(
    api_context: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, sessions = api_context
    created = await create_case(client)
    case_id = UUID(str(created["id"]))

    assert created["status"] == "intake"
    assert created["life_event"]["event_type"] == "parent_death"  # type: ignore[index]
    assert created["household_profile"]["people"][0]["name"] == "Arun Rao"  # type: ignore[index]
    assert created["tasks"] == []
    assert created["documents"] == []

    prerequisite = Task(
        case_id=case_id,
        workflow_id="death_certificate",
        task_type="death_registration",
        status=TaskStatus.COMPLETED,
        title="Obtain death certificate",
    )
    editable = Task(
        case_id=case_id,
        workflow_id="family_pension",
        task_type="family_pension_application",
        status=TaskStatus.READY,
        title="Apply for family pension",
        input_data={"applicant": "Meera Rao"},
    )
    async with sessions() as session:
        session.add_all([prerequisite, editable])
        await session.flush()
        session.add(
            TaskDependency(
                task_id=editable.id,
                depends_on_task_id=prerequisite.id,
                dependency_type="completion",
            )
        )
        session.add(
            Document(
                case_id=case_id,
                produced_by_task_id=editable.id,
                document_type="pension_application_draft",
                owner_name="Meera Rao",
            )
        )
        await session.commit()

    case_response = await client.get(f"/api/cases/{case_id}")
    assert case_response.status_code == 200
    assert len(case_response.json()["tasks"]) == 2
    assert len(case_response.json()["documents"]) == 1

    list_response = await client.get(f"/api/cases/{case_id}/tasks")
    assert list_response.status_code == 200
    listed_statuses = {task["id"]: task["status"] for task in list_response.json()}
    assert listed_statuses[str(prerequisite.id)] == "completed"
    assert listed_statuses[str(editable.id)] == "ready"

    detail_response = await client.get(f"/api/cases/{case_id}/tasks/{editable.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["dependencies"][0]["depends_on_task_id"] == str(prerequisite.id)
    assert detail["produced_documents"][0]["document_type"] == "pension_application_draft"
    assert detail["description"].startswith("Transfer a deceased Karnataka state pensioner")
    assert {document["type"] for document in detail["required_documents"]} == {
        "death_certificate",
        "pension_payment_order",
        "marriage_certificate",
        "spouse_identity",
        "bank_account_proof",
    }

    patch_response = await client.patch(
        f"/api/cases/{case_id}/tasks/{editable.id}",
        json={"input_data": {"field": "value"}},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["input_data"] == {"field": "value"}

    conflict_response = await client.patch(
        f"/api/cases/{case_id}/tasks/{prerequisite.id}",
        json={"input_data": {"field": "value"}},
    )
    assert conflict_response.status_code == 409

    activation_response = await client.post(f"/api/cases/{case_id}/activate")
    assert activation_response.status_code == 200
    assert activation_response.json()["status"] == "active"
    assert (await client.post(f"/api/cases/{case_id}/activate")).status_code == 409


@pytest.mark.anyio
async def test_case_task_api_errors_and_validation(
    api_context: tuple[AsyncClient, async_sessionmaker[AsyncSession]],
) -> None:
    client, _ = api_context
    missing_id = uuid4()

    assert (await client.get(f"/api/cases/{missing_id}")).status_code == 404
    assert (await client.get(f"/api/cases/{missing_id}/tasks")).status_code == 404
    assert (await client.post(f"/api/cases/{missing_id}/activate")).status_code == 404
    assert (await client.post("/api/cases", json={})).status_code == 422
    assert (
        await client.post(
            "/api/cases",
            json={"life_event": {"type": "", "context": {}}},
        )
    ).status_code == 422

    created = await create_case(client)
    case_id = created["id"]
    assert (await client.get(f"/api/cases/{case_id}/tasks/{missing_id}")).status_code == 404
    invalid_patch = await client.patch(
        f"/api/cases/{case_id}/tasks/{missing_id}",
        json={"unexpected": "value"},
    )
    assert invalid_patch.status_code == 422
