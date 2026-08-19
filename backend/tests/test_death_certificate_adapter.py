from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters import (
    AdapterStatus,
    DeathCertificateAdapter,
    GovernmentAdapter,
    UnknownAdapterError,
    get_adapter,
)
from app.db.session import create_database_engine, init_db
from app.models import Case, Document, ExternalApplication, Task, TaskStatus

VALID_PAYLOAD = {
    "deceased_name": "Arun Rao",
    "date_of_death": "2026-08-10",
    "place_of_death": "Bengaluru",
    "cause_of_death": "Natural causes",
    "informant_name": "Meera Rao",
}


@pytest.fixture
async def adapter_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, ExternalApplication]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'adapter.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        case = Case()
        task = Task(
            case=case,
            workflow_id="death_certificate",
            task_type="death_registration",
            status=TaskStatus.SUBMITTED,
            title="Register Death and Obtain Certificate",
        )
        application = ExternalApplication(
            task=task,
            adapter_type="death_certificate",
            request_payload=dict(VALID_PAYLOAD),
        )
        session.add(application)
        await session.flush()
        yield session, application
    await engine.dispose()


@pytest.mark.anyio
async def test_valid_submission_is_approved_and_creates_document(
    adapter_context: tuple[AsyncSession, ExternalApplication],
) -> None:
    session, application = adapter_context
    adapter = DeathCertificateAdapter(session)

    result = await adapter.submit_application(application)

    assert result.status == AdapterStatus.APPROVED
    assert result.reference_id is not None
    assert result.reference_id.startswith("BBMP/D/2026/")
    assert result.response_data == {
        **VALID_PAYLOAD,
        "registration_number": result.reference_id,
        "date_of_registration": "2026-08-10",
        "date_of_issue": "2026-08-10",
        "registrar_name": "Registrar of Births and Deaths, BBMP South Zone",
        "registrar": "Registrar of Births and Deaths, BBMP South Zone",
    }

    document = (await session.scalars(select(Document))).one()
    assert document.case_id == application.task.case_id
    assert document.produced_by_task_id == application.task_id
    assert document.document_type == "death_certificate"
    assert document.owner_name == "Arun Rao"
    assert document.extracted_fields == result.response_data
    assert document.metadata_["reference_id"] == result.reference_id

    status = await adapter.check_status(result.reference_id)
    assert status.status == AdapterStatus.APPROVED
    assert status.response_data == result.response_data


@pytest.mark.anyio
async def test_submission_is_deterministic_and_idempotent(
    adapter_context: tuple[AsyncSession, ExternalApplication],
) -> None:
    session, application = adapter_context
    adapter = DeathCertificateAdapter(session)

    first = await adapter.submit_application(application)
    second = await adapter.submit_application(application)

    assert second == first
    assert await session.scalar(select(func.count()).select_from(Document)) == 1


@pytest.mark.anyio
async def test_missing_field_returns_clear_error_without_document(
    adapter_context: tuple[AsyncSession, ExternalApplication],
) -> None:
    session, application = adapter_context
    application.request_payload = {
        key: value for key, value in VALID_PAYLOAD.items() if key != "deceased_name"
    }

    result = await DeathCertificateAdapter(session).submit_application(application)

    assert result.status == AdapterStatus.ERROR
    assert result.reference_id is None
    assert "deceased_name" in result.message
    assert await session.scalar(select(func.count()).select_from(Document)) == 0


@pytest.mark.anyio
async def test_requirements_registry_and_unknown_reference(
    adapter_context: tuple[AsyncSession, ExternalApplication],
) -> None:
    session, _ = adapter_context
    adapter = get_adapter("death_certificate", session)

    assert isinstance(adapter, DeathCertificateAdapter)
    assert isinstance(adapter, GovernmentAdapter)
    assert await adapter.get_requirements() == [
        "medical_certificate_cause_of_death",
        "deceased_identity",
        "informant_identity",
    ]
    status = await adapter.check_status("BBMP/D/2026/UNKNOWN")
    assert status.status == AdapterStatus.ERROR
    with pytest.raises(UnknownAdapterError, match="unknown_adapter"):
        get_adapter("unknown_adapter", session)
