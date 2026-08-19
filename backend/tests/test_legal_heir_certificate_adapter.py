from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters import (
    AdapterStatus,
    GovernmentAdapter,
    LegalHeirCertificateAdapter,
    get_adapter,
)
from app.db.session import create_database_engine, init_db
from app.models import Case, Document, ExternalApplication, Task, TaskStatus


@pytest.fixture
async def adapter_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, ExternalApplication]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'legal-heir.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        task = Task(
            case=Case(),
            workflow_id="legal_heir_certificate",
            task_type="legal_heir_application",
            status=TaskStatus.SUBMITTED,
            title="Apply for Legal Heir Certificate",
        )
        application = ExternalApplication(
            task=task,
            adapter_type="legal_heir_certificate",
            request_payload={
                "deceased_name": "Arun Rao",
                "legal_heirs": [
                    {"name": "Meera Rao", "relationship": "wife"},
                    {"name": "Kiran Rao", "relationship": "son"},
                ],
            },
        )
        session.add(application)
        await session.flush()
        yield session, application
    await engine.dispose()


@pytest.mark.anyio
async def test_legal_heir_adapter_issues_certificate_and_is_registered(
    adapter_context: tuple[AsyncSession, ExternalApplication],
) -> None:
    session, application = adapter_context
    adapter = get_adapter("legal_heir_certificate", session)

    result = await adapter.submit_application(application)

    assert isinstance(adapter, LegalHeirCertificateAdapter)
    assert isinstance(adapter, GovernmentAdapter)
    assert await adapter.get_requirements() == ["death_certificate", "aadhaar"]
    assert result.status == AdapterStatus.APPROVED
    assert result.reference_id is not None
    assert result.reference_id.startswith("REV/LHC/")
    assert result.response_data["certificate_number"] == result.reference_id
    assert result.response_data["issuing_authority"] == "Tahsildar, Bengaluru South"
    assert result.response_data["legal_heirs"] == application.request_payload["legal_heirs"]
    assert result.response_data["date_of_issue"]

    document = (
        await session.scalars(
            select(Document).where(Document.document_type == "legal_heir_certificate")
        )
    ).one()
    assert document.produced_by_task_id == application.task_id
    assert document.owner_name == "Meera Rao"
    assert document.extracted_fields == result.response_data
