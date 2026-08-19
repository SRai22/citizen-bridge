from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters import AdapterStatus, BescomTransferAdapter, GovernmentAdapter, get_adapter
from app.db.session import create_database_engine, init_db
from app.models import Case, Document, ExternalApplication, Task, TaskStatus

VALID_PAYLOAD = {
    "consumer_number": "BLR-S-JN4-12345",
    "current_holder_name": "Arun Rao",
    "proposed_holder_name": "Meera Rao",
    "property_address": "12 Residency Road, Bengaluru",
}


@pytest.fixture
async def adapter_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, Case, ExternalApplication]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'bescom.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        case = Case()
        task = Task(
            case=case,
            workflow_id="bescom_transfer",
            task_type="bescom_name_transfer",
            status=TaskStatus.SUBMITTED,
            title="Transfer BESCOM Account Holder",
        )
        application = ExternalApplication(
            task=task,
            adapter_type="bescom",
            request_payload=dict(VALID_PAYLOAD),
        )
        session.add_all(
            [
                application,
                Document(
                    case=case,
                    document_type="death_certificate",
                    owner_name="Arun Rao",
                ),
            ]
        )
        await session.flush()
        yield session, case, application
    await engine.dispose()


@pytest.mark.anyio
async def test_submission_without_legal_heir_certificate_is_rejected(
    adapter_context: tuple[AsyncSession, Case, ExternalApplication],
) -> None:
    session, _, application = adapter_context
    result = await BescomTransferAdapter(session).submit_application(application)

    assert result.status == AdapterStatus.REJECTED
    assert result.message == (
        "Supporting documentation establishing the proposed transferee's relationship or "
        "succession rights is insufficient. A Legal Heir Certificate or Succession Certificate "
        "issued by a competent authority is required."
    )
    assert result.response_data == {
        "rejection_code": "INSUFFICIENT_SUCCESSION_DOCS",
        "required_document": "legal_heir_certificate",
    }


@pytest.mark.anyio
async def test_submission_with_legal_heir_certificate_is_approved_deterministically(
    adapter_context: tuple[AsyncSession, Case, ExternalApplication],
) -> None:
    session, case, application = adapter_context
    session.add(
        Document(
            case=case,
            document_type="legal_heir_certificate",
            owner_name="Meera Rao",
        )
    )
    await session.flush()
    adapter = BescomTransferAdapter(session)

    first = await adapter.submit_application(application)
    second = await adapter.submit_application(application)

    assert second == first
    assert first.status == AdapterStatus.APPROVED
    assert first.response_data == {
        "new_account_holder_name": "Meera Rao",
        "effective_date": application.created_at.date().isoformat(),
        "updated_consumer_number": "BLR-S-JN4-12345",
    }


@pytest.mark.anyio
async def test_requirements_and_registry(
    adapter_context: tuple[AsyncSession, Case, ExternalApplication],
) -> None:
    session, _, _ = adapter_context
    adapter = get_adapter("bescom", session)

    assert isinstance(adapter, BescomTransferAdapter)
    assert isinstance(adapter, GovernmentAdapter)
    assert await adapter.get_requirements() == [
        "death_certificate",
        "legal_heir_certificate",
    ]
