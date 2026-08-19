from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters import (
    AdapterStatus,
    FamilyPensionAdapter,
    GovernmentAdapter,
    RationCardAdapter,
    get_adapter,
)
from app.db.session import create_database_engine, init_db
from app.models import Case, Document, ExternalApplication, Task, TaskStatus


@pytest.fixture
async def adapter_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, Case, ExternalApplication, ExternalApplication]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'pension-ration.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        case = Case()
        pension_task = Task(
            case=case,
            workflow_id="family_pension",
            task_type="family_pension_application",
            status=TaskStatus.SUBMITTED,
            title="Apply for Family Pension",
        )
        ration_task = Task(
            case=case,
            workflow_id="ration_card",
            task_type="ration_card_modification",
            status=TaskStatus.SUBMITTED,
            title="Update Ration Card Household",
        )
        pension_application = ExternalApplication(
            task=pension_task,
            adapter_type="family_pension",
            request_payload={
                "spouse_name": "Meera Rao",
                "ppo_number": "KAR/PPO/12345",
                "bank_account_number": "1234567890",
            },
        )
        ration_application = ExternalApplication(
            task=ration_task,
            adapter_type="ration_card",
            request_payload={
                "ration_card_number": "KA-BLR-1234567",
                "deceased_name": "Arun Rao",
                "new_head_name": "Meera Rao",
            },
        )
        session.add_all(
            [
                pension_application,
                ration_application,
                Document(
                    case=case,
                    document_type="death_certificate",
                    owner_name="Arun Rao",
                    extracted_fields={"date_of_death": "2026-08-10"},
                ),
                Document(
                    case=case,
                    document_type="pension_payment_order",
                    owner_name="Arun Rao",
                    extracted_fields={"ppo_number": "KAR/PPO/12345"},
                ),
            ]
        )
        await session.flush()
        yield session, case, pension_application, ration_application
    await engine.dispose()


@pytest.mark.anyio
async def test_pension_and_ration_submissions_create_reusable_documents(
    adapter_context: tuple[AsyncSession, Case, ExternalApplication, ExternalApplication],
) -> None:
    session, _, pension_application, ration_application = adapter_context

    pension = await FamilyPensionAdapter(session).submit_application(pension_application)
    ration = await RationCardAdapter(session).submit_application(ration_application)

    assert pension.status == AdapterStatus.APPROVED
    assert pension.reference_id is not None
    assert pension.response_data == {
        "provisional_pension_amount": 25_000,
        "effective_date": "2026-08-11",
        "ppo_number": pension.reference_id,
        "treasury_code": "BLR-SOUTH",
    }
    assert ration.status == AdapterStatus.APPROVED
    assert ration.reference_id is not None
    assert ration.response_data == {
        "updated_card_number": ration.reference_id,
        "new_head_of_family": "Meera Rao",
        "modification_type": "member_deletion + head_change",
    }

    produced = list(
        (
            await session.scalars(select(Document).where(Document.produced_by_task_id.is_not(None)))
        ).all()
    )
    assert {document.document_type for document in produced} == {
        "family_pension_sanction",
        "updated_ration_card",
    }
    assert {document.document_type: document.extracted_fields for document in produced} == {
        "family_pension_sanction": pension.response_data,
        "updated_ration_card": ration.response_data,
    }


@pytest.mark.anyio
async def test_registry_requirements_and_missing_death_certificate(
    adapter_context: tuple[AsyncSession, Case, ExternalApplication, ExternalApplication],
) -> None:
    session, _, pension_application, ration_application = adapter_context
    pension = get_adapter("family_pension", session)
    ration = get_adapter("ration_card", session)

    assert isinstance(pension, FamilyPensionAdapter)
    assert isinstance(ration, RationCardAdapter)
    assert isinstance(pension, GovernmentAdapter)
    assert isinstance(ration, GovernmentAdapter)
    assert await pension.get_requirements() == [
        "death_certificate",
        "pension_payment_order",
    ]
    assert await ration.get_requirements() == ["death_certificate"]

    death_certificate = await session.scalar(
        select(Document).where(Document.document_type == "death_certificate")
    )
    assert death_certificate is not None
    await session.delete(death_certificate)
    await session.flush()

    pension_result = await pension.submit_application(pension_application)
    ration_result = await ration.submit_application(ration_application)
    assert pension_result.status == AdapterStatus.ERROR
    assert "death_certificate" in pension_result.message
    assert ration_result.status == AdapterStatus.ERROR
    assert "death_certificate" in ration_result.message
