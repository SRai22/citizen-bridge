from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import (
    CaseNotFoundError,
    InvalidStateTransitionError,
    WorkflowEngine,
    WorkflowTaskNotFoundError,
)
from app.db.base import Base
from app.db.session import create_database_engine, init_db
from app.models import AuditEntry, Case, CaseStatus, Task, TaskDependency, TaskStatus

DEMO_PROFILE: dict[str, object] = {
    "deceased": {
        "is_deceased": True,
        "pension_status": "active",
        "was_electricity_account_holder": True,
        "was_head_of_household": True,
    },
    "location": {"state": "Karnataka"},
    "surviving_spouse": {"exists": True},
    "assets": {"bescom": True, "ration_card": True},
}


@pytest.fixture
async def engine_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, WorkflowEngine, Case]]:
    database_engine = create_database_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'workflow-engine.db'}"
    )
    await init_db(database_engine)
    sessions = async_sessionmaker(database_engine, expire_on_commit=False)
    async with sessions() as session:
        case = Case(status=CaseStatus.ACTIVE)
        session.add(case)
        await session.commit()
        yield session, WorkflowEngine(session), case
    await database_engine.dispose()


def task_by_workflow(tasks: list[Task], workflow_id: str) -> Task:
    return next(task for task in tasks if task.workflow_id == workflow_id)


@pytest.mark.anyio
async def test_applicability_and_idempotent_activation(
    engine_context: tuple[AsyncSession, WorkflowEngine, Case],
) -> None:
    session, engine, case = engine_context

    applicable = engine.get_applicable_workflows(DEMO_PROFILE)
    assert {definition.id for definition in applicable} == {
        "death_certificate",
        "family_pension",
        "bescom_transfer",
        "ration_card",
    }

    tasks = await engine.activate_workflows(case.id, DEMO_PROFILE)
    death_certificate = task_by_workflow(tasks, "death_certificate")
    assert len(tasks) == 4
    assert death_certificate.task_type == "death_registration"
    assert death_certificate.status == TaskStatus.READY
    assert all(
        task.status == TaskStatus.PENDING for task in tasks if task.id != death_certificate.id
    )

    dependencies = list((await session.scalars(select(TaskDependency))).all())
    assert len(dependencies) == 3
    assert {dependency.depends_on_task_id for dependency in dependencies} == {death_certificate.id}

    repeated_tasks = await engine.activate_workflows(case.id, DEMO_PROFILE)
    assert {task.id for task in repeated_tasks} == {task.id for task in tasks}
    assert await session.scalar(select(func.count()).select_from(Task)) == 4
    assert await session.scalar(select(func.count()).select_from(TaskDependency)) == 3


@pytest.mark.anyio
async def test_transitions_complete_upstream_and_cascade_readiness(
    engine_context: tuple[AsyncSession, WorkflowEngine, Case],
) -> None:
    session, engine, case = engine_context
    tasks = await engine.activate_workflows(case.id, DEMO_PROFILE)
    death_certificate = task_by_workflow(tasks, "death_certificate")

    await engine.transition_task(
        death_certificate.id,
        TaskStatus.IN_PROGRESS,
        {"actor": "citizen"},
    )
    await engine.transition_task(death_certificate.id, TaskStatus.SUBMITTED, {})
    completed = await engine.transition_task(
        death_certificate.id,
        TaskStatus.COMPLETED,
        {"external_reference": "BBMP-100"},
    )

    assert completed.completed_at is not None
    persisted_tasks = list(
        (await session.scalars(select(Task).where(Task.case_id == case.id))).all()
    )
    assert task_by_workflow(persisted_tasks, "death_certificate").status == TaskStatus.COMPLETED
    assert all(
        task.status == TaskStatus.READY
        for task in persisted_tasks
        if task.workflow_id != "death_certificate"
    )

    audits = list(
        (
            await session.scalars(
                select(AuditEntry)
                .where(AuditEntry.case_id == case.id)
                .order_by(AuditEntry.created_at)
            )
        ).all()
    )
    assert len(audits) == 7
    assert audits[-1].details["transition"] == {"from": "pending", "to": "ready"}
    assert any(audit.details["context"].get("actor") == "citizen" for audit in audits)


@pytest.mark.anyio
async def test_direct_auto_approved_submission_is_supported(
    engine_context: tuple[AsyncSession, WorkflowEngine, Case],
) -> None:
    _, engine, case = engine_context
    tasks = await engine.activate_workflows(case.id, DEMO_PROFILE)
    death_certificate = task_by_workflow(tasks, "death_certificate")

    submitted = await engine.transition_task(death_certificate.id, TaskStatus.SUBMITTED, {})

    assert submitted.status == TaskStatus.SUBMITTED


@pytest.mark.anyio
async def test_invalid_transition_has_current_and_attempted_states(
    engine_context: tuple[AsyncSession, WorkflowEngine, Case],
) -> None:
    _, engine, case = engine_context
    tasks = await engine.activate_workflows(case.id, DEMO_PROFILE)
    pending = task_by_workflow(tasks, "family_pension")

    with pytest.raises(InvalidStateTransitionError) as captured:
        await engine.transition_task(pending.id, TaskStatus.SUBMITTED, {})

    assert captured.value.current_status == TaskStatus.PENDING
    assert captured.value.attempted_status == TaskStatus.SUBMITTED
    assert pending.status == TaskStatus.PENDING


@pytest.mark.anyio
async def test_missing_case_and_task_raise_domain_errors(
    engine_context: tuple[AsyncSession, WorkflowEngine, Case],
) -> None:
    _, engine, _ = engine_context
    with pytest.raises(CaseNotFoundError):
        await engine.activate_workflows(uuid4(), DEMO_PROFILE)
    with pytest.raises(WorkflowTaskNotFoundError):
        await engine.transition_task(uuid4(), TaskStatus.READY, {})


@pytest.mark.anyio
async def test_engine_tests_leave_schema_registered() -> None:
    assert "tasks" in Base.metadata.tables
