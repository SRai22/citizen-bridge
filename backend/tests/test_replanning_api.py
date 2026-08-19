from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import RejectionInterpreter
from app.db.session import create_database_engine, get_session, init_db
from app.main import create_app
from app.models import Case, CaseStatus, Document, Task, TaskDependency, TaskStatus


@pytest.fixture
async def replanning_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession], Case, Task]]:
    monkeypatch.setenv("MOCK_AI", "true")
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'replanning.db'}")
    await init_db(engine)
    database_sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with database_sessions() as session:
        case = Case(status=CaseStatus.ACTIVE)
        death_task = Task(
            case=case,
            workflow_id="death_certificate",
            task_type="death_registration",
            status=TaskStatus.COMPLETED,
            title="Register Death and Obtain Certificate",
        )
        bescom_task = Task(
            case=case,
            workflow_id="bescom_transfer",
            task_type="bescom_name_transfer",
            status=TaskStatus.READY,
            title="Transfer BESCOM Account Holder",
            input_data={
                "consumer_number": "BLR-S-JN4-12345",
                "current_holder_name": "Arun Rao",
                "proposed_holder_name": "Meera Rao",
                "property_address": "12 Residency Road, Bengaluru",
            },
        )
        session.add_all([case, death_task, bescom_task])
        await session.flush()
        session.add(
            TaskDependency(
                task_id=bescom_task.id,
                depends_on_task_id=death_task.id,
            )
        )
        session.add_all(
            [
                Document(case_id=case.id, document_type=document_type, owner_name="Arun Rao")
                for document_type in (
                    "death_certificate",
                    "electricity_bill",
                    "property_occupancy_proof",
                    "applicant_identity",
                )
            ]
        )
        await session.commit()

    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with database_sessions() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        yield client, database_sessions, case, bescom_task
    await engine.dispose()


@pytest.mark.anyio
async def test_bescom_rejection_is_interpreted_and_replanned_idempotently(
    replanning_context: tuple[
        AsyncClient,
        async_sessionmaker[AsyncSession],
        Case,
        Task,
    ],
) -> None:
    client, database_sessions, case, bescom_task = replanning_context

    prepared = await client.post(f"/api/cases/{case.id}/tasks/{bescom_task.id}/prepare")
    assert prepared.status_code == 200
    rejected = await client.post(f"/api/approvals/{prepared.json()['id']}/approve")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    interpreted = await client.post(
        f"/api/cases/{case.id}/tasks/{bescom_task.id}/interpret-rejection"
    )
    assert interpreted.status_code == 200
    interpretation = interpreted.json()
    assert interpretation["cause"] == "missing_legal_heir_certificate"
    assert "Legal Heir Certificate" in interpretation["explanation"]
    assert interpretation["remediation"] == {
        "action": "add_task",
        "workflow_id": "legal_heir_certificate",
        "dependency_target": "bescom_transfer",
    }

    accepted = await client.post(
        f"/api/cases/{case.id}/accept-remediation",
        json=interpretation["remediation"],
    )
    assert accepted.status_code == 200
    tasks = {task["workflow_id"]: task for task in accepted.json()["tasks"]}
    assert tasks["legal_heir_certificate"]["status"] == "ready"
    assert tasks["bescom_transfer"]["status"] == "blocked"
    legal_task_id = tasks["legal_heir_certificate"]["id"]
    assert legal_task_id in {
        dependency["depends_on_task_id"] for dependency in tasks["bescom_transfer"]["dependencies"]
    }

    repeated = await client.post(
        f"/api/cases/{case.id}/accept-remediation",
        json=interpretation["remediation"],
    )
    assert repeated.status_code == 200
    async with database_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Task)) == 3
        assert await session.scalar(select(func.count()).select_from(TaskDependency)) == 3
        session.add(
            Document(
                case_id=case.id,
                document_type="aadhaar",
                owner_name="Meera Rao",
            )
        )
        await session.commit()

    legal_input = await client.patch(
        f"/api/cases/{case.id}/tasks/{legal_task_id}",
        json={
            "input_data": {
                "deceased_name": "Arun Rao",
                "legal_heirs": [
                    {"name": "Meera Rao", "relationship": "wife"},
                    {"name": "Kiran Rao", "relationship": "son"},
                ],
            }
        },
    )
    assert legal_input.status_code == 200
    legal_prepared = await client.post(f"/api/cases/{case.id}/tasks/{legal_task_id}/prepare")
    assert legal_prepared.status_code == 200
    legal_approved = await client.post(f"/api/approvals/{legal_prepared.json()['id']}/approve")
    assert legal_approved.status_code == 200
    assert legal_approved.json()["status"] == "approved"

    bescom_prepared = await client.post(f"/api/cases/{case.id}/tasks/{bescom_task.id}/prepare")
    assert bescom_prepared.status_code == 200
    bescom_approved = await client.post(f"/api/approvals/{bescom_prepared.json()['id']}/approve")
    assert bescom_approved.status_code == 200
    assert bescom_approved.json()["status"] == "approved"

    async with database_sessions() as session:
        legal_certificate = await session.scalar(
            select(Document).where(Document.document_type == "legal_heir_certificate")
        )
        assert legal_certificate is not None
        assert legal_certificate.extracted_fields["issuing_authority"] == (
            "Tahsildar, Bengaluru South"
        )


@pytest.mark.anyio
async def test_mock_interpreter_handles_an_unclear_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_AI", "true")

    interpretation = await RejectionInterpreter().interpret("???", {"workflow_id": "bescom"})

    assert interpretation.explanation
    assert interpretation.confidence > 0


@pytest.mark.anyio
async def test_openai_interpretation_uses_strict_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MOCK_AI", "false")
    content = """{
        "cause": "missing_document",
        "explanation": "A supporting document is required.",
        "confidence": 0.8,
        "remediation": {
            "action": "add_task",
            "workflow_id": "legal_heir_certificate",
            "dependency_target": "bescom_transfer"
        }
    }"""
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    result = await RejectionInterpreter(cast(Any, client)).interpret(
        "Missing supporting document",
        {"workflow_id": "bescom_transfer"},
    )

    response_format = create.await_args.kwargs["response_format"]
    assert result.cause == "missing_document"
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert "remediation" in response_format["json_schema"]["schema"]["properties"]
