from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import (
    InvalidApprovalStateError,
    MissingRequiredDocumentsError,
    SubmissionService,
    WorkflowDefinition,
    WorkflowLoader,
)
from app.db.session import create_database_engine, init_db
from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    Case,
    Document,
    ExternalApplication,
    ExternalApplicationStatus,
    Task,
    TaskDependency,
    TaskStatus,
)

REQUIRED_DOCUMENTS = (
    "medical_certificate_cause_of_death",
    "deceased_identity",
    "informant_identity",
)
VALID_INPUT = {
    "deceased_name": "Arun Rao",
    "date_of_death": "2026-08-10",
    "place_of_death": "Bengaluru",
    "cause_of_death": "Natural causes",
}


class NoApprovalWorkflowLoader(WorkflowLoader):
    def load_all(self) -> list[WorkflowDefinition]:
        definitions = super().load_all()
        death_certificate = next(
            definition for definition in definitions if definition.id == "death_certificate"
        )
        task = death_certificate.tasks[0].model_copy(update={"requires_approval": False})
        return [death_certificate.model_copy(update={"tasks": [task]})]


@pytest.fixture
async def submission_context(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncSession, SubmissionService, Case, Task, Task]]:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'submission.db'}")
    await init_db(engine)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        case = Case()
        upstream = Task(
            case=case,
            workflow_id="death_certificate",
            task_type="death_registration",
            status=TaskStatus.READY,
            title="Register Death and Obtain Certificate",
            input_data=dict(VALID_INPUT),
        )
        downstream = Task(
            case=case,
            workflow_id="family_pension",
            task_type="family_pension_application",
            status=TaskStatus.PENDING,
            title="Apply for Family Pension",
        )
        session.add_all([case, upstream, downstream])
        await session.flush()
        session.add(
            TaskDependency(task_id=downstream.id, depends_on_task_id=upstream.id)
        )
        session.add_all(
            [
                Document(
                    case_id=case.id,
                    document_type=document_type,
                    owner_name="Arun Rao",
                )
                for document_type in REQUIRED_DOCUMENTS
            ]
        )
        await session.commit()
        yield session, SubmissionService(session), case, upstream, downstream
    await engine.dispose()


@pytest.mark.anyio
async def test_approved_submission_completes_task_and_unblocks_dependents(
    submission_context: tuple[AsyncSession, SubmissionService, Case, Task, Task],
) -> None:
    session, service, case, upstream, downstream = submission_context

    outcome = await service.prepare(upstream.id)

    assert isinstance(outcome, ApprovalRequest)
    assert outcome.status == ApprovalStatus.PENDING
    assert outcome.context["summary"].startswith("Review and submit")
    assert outcome.context["input_data"] == VALID_INPUT
    assert upstream.status == TaskStatus.AWAITING_APPROVAL

    application = await service.approve(outcome.id)

    assert outcome.status == ApprovalStatus.APPROVED
    assert outcome.resolved_at is not None
    assert application.status == ExternalApplicationStatus.APPROVED
    assert application.external_reference_id is not None
    assert application.response_payload["data"]["deceased_name"] == "Arun Rao"
    assert upstream.status == TaskStatus.COMPLETED
    assert upstream.completed_at is not None
    assert downstream.status == TaskStatus.READY
    assert await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.document_type == "death_certificate")
    ) == 1

    event_types = set(
        (
            await session.scalars(
                select(AuditEntry.event_type).where(AuditEntry.case_id == case.id)
            )
        ).all()
    )
    assert {
        "approval_requested",
        "approval_approved",
        "submission_sent",
        "submission_result_received",
        "task_status_changed",
    } <= event_types
    assert await service.list_approvals(case.id) == [outcome]


@pytest.mark.anyio
async def test_rejected_approval_returns_task_to_ready_without_submission(
    submission_context: tuple[AsyncSession, SubmissionService, Case, Task, Task],
) -> None:
    session, service, _, upstream, _ = submission_context
    outcome = await service.prepare(upstream.id)
    assert isinstance(outcome, ApprovalRequest)

    rejected = await service.reject(outcome.id)

    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.resolved_at is not None
    assert upstream.status == TaskStatus.READY
    assert await session.scalar(select(func.count()).select_from(ExternalApplication)) == 0
    with pytest.raises(InvalidApprovalStateError, match="already rejected"):
        await service.reject(outcome.id)


@pytest.mark.anyio
async def test_missing_documents_prevent_preparation(
    submission_context: tuple[AsyncSession, SubmissionService, Case, Task, Task],
) -> None:
    session, service, _, upstream, _ = submission_context
    document = await session.scalar(
        select(Document).where(Document.document_type == "informant_identity")
    )
    assert document is not None
    await session.delete(document)
    await session.commit()

    with pytest.raises(MissingRequiredDocumentsError) as captured:
        await service.prepare(upstream.id)

    assert captured.value.missing_document_types == ["informant_identity"]
    assert upstream.status == TaskStatus.READY


@pytest.mark.anyio
async def test_adapter_error_is_persisted_and_marks_task_failed(
    submission_context: tuple[AsyncSession, SubmissionService, Case, Task, Task],
) -> None:
    _, service, _, upstream, downstream = submission_context
    upstream.input_data = {}
    outcome = await service.prepare(upstream.id)
    assert isinstance(outcome, ApprovalRequest)

    application = await service.approve(outcome.id)

    assert application.status == ExternalApplicationStatus.ERROR
    assert "Missing required application fields" in application.response_payload["message"]
    assert upstream.status == TaskStatus.FAILED
    assert downstream.status == TaskStatus.PENDING


@pytest.mark.anyio
async def test_task_without_approval_requirement_submits_immediately(
    submission_context: tuple[AsyncSession, SubmissionService, Case, Task, Task],
) -> None:
    session, _, _, upstream, downstream = submission_context
    service = SubmissionService(session, workflow_loader=NoApprovalWorkflowLoader())

    outcome = await service.prepare(upstream.id)

    assert isinstance(outcome, ExternalApplication)
    assert outcome.status == ExternalApplicationStatus.APPROVED
    assert upstream.status == TaskStatus.COMPLETED
    assert downstream.status == TaskStatus.READY
    assert await session.scalar(select(func.count()).select_from(ApprovalRequest)) == 0
