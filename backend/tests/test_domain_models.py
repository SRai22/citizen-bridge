from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.base import Base
from app.db.session import create_database_engine, init_db
from app.models import (
    ApprovalRequest,
    AuditEntry,
    Case,
    CaseStatus,
    Document,
    ExternalApplication,
    HouseholdProfile,
    LifeEvent,
    Person,
    Task,
    TaskDependency,
    TaskStatus,
    VerificationStatus,
)
from app.schemas import CaseRead


@pytest.fixture
async def database_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await init_db(engine)
    yield engine
    await engine.dispose()


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.anyio
async def test_case_graph_round_trip_and_cascade(database_engine: AsyncEngine) -> None:
    sessions = make_session_factory(database_engine)

    upstream = Task(
        workflow_id="death_certificate",
        task_type="death_registration",
        status=TaskStatus.COMPLETED,
        title="Obtain death certificate",
        output_data={"certificate": {"number": "DC-100", "verified": True}},
    )
    downstream = Task(
        workflow_id="family_pension",
        task_type="pension_application",
        status=TaskStatus.PENDING,
        title="Apply for family pension",
        input_data={"applicant": {"relationship": "spouse"}},
    )
    dependency = TaskDependency(
        task=downstream,
        depends_on_task=upstream,
        dependency_type="document",
    )
    upstream.external_applications.append(
        ExternalApplication(
            adapter_type="death_certificate_adapter",
            external_reference_id="BBMP-100",
            request_payload={"person": {"name": "Arun Rao"}},
            response_payload={"accepted": True},
        )
    )
    downstream.approval_requests.append(
        ApprovalRequest(
            action_description="Submit family pension application",
            context={"declared_members": ["Meera Rao", "Kiran Rao"]},
        )
    )
    case = Case(
        status=CaseStatus.ACTIVE,
        life_event=LifeEvent(
            event_type="parent_death",
            context={"source": "intake", "confidence": 0.98},
        ),
        household_profile=HouseholdProfile(
            location_city="Bengaluru",
            location_state="Karnataka",
            people=[
                Person(
                    name="Arun Rao",
                    relationship="father",
                    role="head_of_family",
                    is_deceased=True,
                    attributes={"pension": {"type": "state", "active": True}},
                )
            ],
        ),
        tasks=[upstream, downstream],
    )
    case.documents.append(
        Document(
            produced_by_task=upstream,
            document_type="death_certificate",
            owner_name="Arun Rao",
            issuer="BBMP",
            verification_status=VerificationStatus.VERIFIED,
            extracted_fields={"registration": {"number": "DC-100"}},
            metadata_={"source": "mock_adapter", "tags": ["official", "reusable"]},
        )
    )
    case.audit_entries.append(
        AuditEntry(
            task=upstream,
            event_type="task_status_changed",
            description="Death certificate task completed",
            details={"transition": {"from": "submitted", "to": "completed"}},
        )
    )

    async with sessions() as session:
        session.add_all([case, dependency])
        await session.commit()
        case_id = case.id

    async with sessions() as session:
        session.add(
            TaskDependency(
                task_id=downstream.id,
                depends_on_task_id=upstream.id,
                dependency_type="completion",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    eager_case = (
        select(Case)
        .where(Case.id == case_id)
        .options(
            selectinload(Case.life_event),
            selectinload(Case.household_profile).selectinload(HouseholdProfile.people),
            selectinload(Case.tasks).selectinload(Task.dependencies),
            selectinload(Case.tasks).selectinload(Task.external_applications),
            selectinload(Case.tasks).selectinload(Task.approval_requests),
            selectinload(Case.documents),
            selectinload(Case.audit_entries),
        )
    )
    async with sessions() as session:
        loaded = (await session.scalars(eager_case)).one()

        assert loaded.household_profile is not None
        assert loaded.household_profile.people[0].attributes["pension"]["type"] == "state"
        assert len(loaded.tasks) == 2
        loaded_downstream = next(
            task for task in loaded.tasks if task.task_type == "pension_application"
        )
        assert loaded_downstream.dependencies[0].depends_on_task_id == upstream.id
        assert loaded.documents[0].metadata_["tags"] == ["official", "reusable"]

        response = CaseRead.model_validate(loaded)
        assert response.documents[0].metadata["source"] == "mock_adapter"
        assert response.tasks[0].created_at is not None

    async with sessions() as session:
        persisted_case = await session.get(Case, case_id)
        assert persisted_case is not None
        await session.delete(persisted_case)
        await session.commit()

        for model in Base.metadata.sorted_tables:
            count = await session.scalar(select(func.count()).select_from(model))
            assert count == 0, f"Rows remain in {model.name} after deleting the case"


@pytest.mark.anyio
async def test_uuid_generation_has_no_collisions(database_engine: AsyncEngine) -> None:
    sessions = make_session_factory(database_engine)
    cases = [Case() for _ in range(100)]

    async with sessions() as session:
        session.add_all(cases)
        await session.commit()

    identifiers = {case.id for case in cases}
    assert len(identifiers) == 100
    assert all(isinstance(identifier, UUID) for identifier in identifiers)
