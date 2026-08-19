from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import create_database_engine, get_session, init_db
from app.main import create_app
from app.models import Case, Document, Task, TaskStatus


@pytest.fixture
async def submission_api_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession], Case, Task]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'submission-api.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    case = Case()
    task = Task(
        case=case,
        workflow_id="death_certificate",
        task_type="death_registration",
        status=TaskStatus.READY,
        title="Register Death and Obtain Certificate",
        input_data={
            "deceased_name": "Arun Rao",
            "date_of_death": "2026-08-10",
            "place_of_death": "Bengaluru",
            "cause_of_death": "Natural causes",
        },
    )
    async with sessions() as session:
        session.add(case)
        await session.flush()
        session.add_all(
            [
                Document(case_id=case.id, document_type=document_type, owner_name="Arun Rao")
                for document_type in (
                    "medical_certificate_cause_of_death",
                    "deceased_identity",
                    "informant_identity",
                )
            ]
        )
        await session.commit()

    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield client, sessions, case, task
    await engine.dispose()


@pytest.mark.anyio
async def test_prepare_list_and_approve_submission_api(
    submission_api_context: tuple[
        AsyncClient,
        async_sessionmaker[AsyncSession],
        Case,
        Task,
    ],
) -> None:
    client, _, case, task = submission_api_context

    prepare = await client.post(f"/api/cases/{case.id}/tasks/{task.id}/prepare")
    assert prepare.status_code == 200
    approval = prepare.json()
    assert approval["status"] == "pending"

    approvals = await client.get(f"/api/cases/{case.id}/approvals")
    assert approvals.status_code == 200
    assert [item["id"] for item in approvals.json()] == [approval["id"]]

    approved = await client.post(f"/api/approvals/{approval['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["external_reference_id"].startswith("BBMP/D/2026/")

    repeated = await client.post(f"/api/approvals/{approval['id']}/approve")
    assert repeated.status_code == 409


@pytest.mark.anyio
async def test_prepare_api_reports_missing_documents(
    submission_api_context: tuple[
        AsyncClient,
        async_sessionmaker[AsyncSession],
        Case,
        Task,
    ],
) -> None:
    client, sessions, case, task = submission_api_context
    async with sessions() as session:
        document = await session.scalar(
            select(Document).where(Document.document_type == "deceased_identity")
        )
        assert document is not None
        await session.delete(document)
        await session.commit()

    response = await client.post(f"/api/cases/{case.id}/tasks/{task.id}/prepare")

    assert response.status_code == 422
    assert response.json()["detail"]["missing_document_types"] == ["deceased_identity"]
