"""Approval-gated task submission orchestration."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import AdapterStatus, GovernmentAdapter, get_adapter
from app.core.workflow_engine import WorkflowEngine
from app.core.workflow_loader import WorkflowLoader
from app.core.workflow_schema import TaskDefinition, WorkflowDefinition
from app.db.base import utc_now
from app.models import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEntry,
    Document,
    ExternalApplication,
    ExternalApplicationStatus,
    Task,
    TaskStatus,
)

AdapterFactory = Callable[[str, AsyncSession], GovernmentAdapter]
PreparationOutcome = ApprovalRequest | ExternalApplication


class SubmissionServiceError(ValueError):
    """Base class for submission workflow errors."""


class SubmissionTaskNotFoundError(SubmissionServiceError):
    """Raised when a submission targets a missing task."""


class SubmissionDefinitionError(SubmissionServiceError):
    """Raised when a task cannot be matched to its static definition."""


class InvalidSubmissionStateError(SubmissionServiceError):
    """Raised when preparation is attempted from an invalid task state."""


class MissingRequiredDocumentsError(SubmissionServiceError):
    """Raised when a case lacks documents required for submission."""

    def __init__(self, missing_document_types: list[str]) -> None:
        self.missing_document_types = missing_document_types
        super().__init__(
            f"Missing required documents: {', '.join(missing_document_types)}"
        )


class ApprovalNotFoundError(SubmissionServiceError):
    """Raised when an approval request does not exist."""


class InvalidApprovalStateError(SubmissionServiceError):
    """Raised when an approval has already been resolved or is inconsistent."""


ADAPTER_STATUS_MAP: dict[AdapterStatus, ExternalApplicationStatus] = {
    AdapterStatus.SUBMITTED: ExternalApplicationStatus.SUBMITTED,
    AdapterStatus.PROCESSING: ExternalApplicationStatus.PROCESSING,
    AdapterStatus.APPROVED: ExternalApplicationStatus.APPROVED,
    AdapterStatus.REJECTED: ExternalApplicationStatus.REJECTED,
    AdapterStatus.ERROR: ExternalApplicationStatus.ERROR,
}


class SubmissionService:
    """Coordinate document checks, approvals, adapters, and task transitions."""

    def __init__(
        self,
        session: AsyncSession,
        workflow_engine: WorkflowEngine | None = None,
        workflow_loader: WorkflowLoader | None = None,
        adapter_factory: AdapterFactory = get_adapter,
    ) -> None:
        self.session = session
        self.workflow_engine = workflow_engine or WorkflowEngine(session)
        self.workflow_loader = workflow_loader or WorkflowLoader()
        self.adapter_factory = adapter_factory

    async def prepare(self, task_id: UUID) -> PreparationOutcome:
        """Validate a task and either request approval or submit immediately."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise SubmissionTaskNotFoundError(f"Task not found: {task_id}")
        if task.status not in {TaskStatus.READY, TaskStatus.IN_PROGRESS}:
            raise InvalidSubmissionStateError(
                f"Cannot prepare task {task_id} in {task.status.value} status"
            )

        workflow, task_definition = self._definition_for_task(task)
        await self._validate_required_documents(task, task_definition)
        await self._ensure_no_pending_approval(task.id)

        try:
            if task.status == TaskStatus.READY:
                await self.workflow_engine.transition_task(
                    task.id,
                    TaskStatus.IN_PROGRESS,
                    {"reason": "submission_preparation"},
                    commit=False,
                )

            if task_definition.requires_approval:
                approval = ApprovalRequest(
                    task_id=task.id,
                    action_description=f"Submit {task.title} to {workflow.authority}",
                    status=ApprovalStatus.PENDING,
                    context={
                        "summary": f"Review and submit {task.title} to {workflow.authority}.",
                        "adapter_type": workflow.adapter_type,
                        "input_data": dict(task.input_data),
                        "required_documents": [
                            requirement.type
                            for requirement in task_definition.required_documents
                        ],
                    },
                )
                self.session.add(approval)
                await self.session.flush()
                await self.workflow_engine.transition_task(
                    task.id,
                    TaskStatus.AWAITING_APPROVAL,
                    {"approval_id": str(approval.id)},
                    commit=False,
                )
                self._add_audit(
                    task,
                    "approval_requested",
                    f"Approval requested for '{task.title}'",
                    {"approval_id": str(approval.id)},
                )
                await self.session.commit()
                return approval

            application = await self._execute_submission(task, workflow)
            await self.session.commit()
            return application
        except Exception:
            await self.session.rollback()
            raise

    async def approve(self, approval_id: UUID) -> ExternalApplication:
        """Approve a pending request and execute its government submission."""
        approval, task = await self._pending_approval(approval_id)
        workflow, _ = self._definition_for_task(task)

        try:
            approval.status = ApprovalStatus.APPROVED
            approval.resolved_at = utc_now()
            self._add_audit(
                task,
                "approval_approved",
                f"Submission approved for '{task.title}'",
                {"approval_id": str(approval.id)},
            )
            application = await self._execute_submission(task, workflow)
            await self.session.commit()
            return application
        except Exception:
            await self.session.rollback()
            raise

    async def reject(self, approval_id: UUID) -> ApprovalRequest:
        """Reject a pending request and return its task to ready."""
        approval, task = await self._pending_approval(approval_id)
        try:
            approval.status = ApprovalStatus.REJECTED
            approval.resolved_at = utc_now()
            self._add_audit(
                task,
                "approval_rejected",
                f"Submission approval rejected for '{task.title}'",
                {"approval_id": str(approval.id)},
            )
            await self.workflow_engine.transition_task(
                task.id,
                TaskStatus.READY,
                {"approval_id": str(approval.id), "reason": "approval_rejected"},
                commit=False,
            )
            await self.session.commit()
            return approval
        except Exception:
            await self.session.rollback()
            raise

    async def list_approvals(self, case_id: UUID) -> list[ApprovalRequest]:
        result = await self.session.scalars(
            select(ApprovalRequest)
            .join(Task, ApprovalRequest.task_id == Task.id)
            .where(Task.case_id == case_id)
            .order_by(ApprovalRequest.requested_at, ApprovalRequest.id)
        )
        return list(result.all())

    async def _execute_submission(
        self,
        task: Task,
        workflow: WorkflowDefinition,
    ) -> ExternalApplication:
        await self.workflow_engine.transition_task(
            task.id,
            TaskStatus.SUBMITTED,
            {"adapter_type": workflow.adapter_type},
            commit=False,
        )
        application = ExternalApplication(
            task_id=task.id,
            adapter_type=workflow.adapter_type,
            status=ExternalApplicationStatus.SUBMITTED,
            request_payload=dict(task.input_data),
            submitted_at=utc_now(),
        )
        self.session.add(application)
        await self.session.flush()
        self._add_audit(
            task,
            "submission_sent",
            f"'{task.title}' submitted to {workflow.authority}",
            {
                "application_id": str(application.id),
                "adapter_type": workflow.adapter_type,
            },
        )

        adapter = self.adapter_factory(workflow.adapter_type, self.session)
        result = await adapter.submit_application(application)
        application.external_reference_id = result.reference_id
        application.status = ADAPTER_STATUS_MAP[result.status]
        application.response_payload = {
            "message": result.message,
            "data": result.response_data,
        }
        application.responded_at = utc_now()

        if result.status == AdapterStatus.APPROVED:
            await self.workflow_engine.transition_task(
                task.id,
                TaskStatus.COMPLETED,
                {
                    "application_id": str(application.id),
                    "external_reference_id": result.reference_id,
                },
                commit=False,
            )
        elif result.status in {AdapterStatus.REJECTED, AdapterStatus.ERROR}:
            await self.workflow_engine.transition_task(
                task.id,
                TaskStatus.FAILED,
                {
                    "application_id": str(application.id),
                    "adapter_status": result.status.value,
                },
                commit=False,
            )

        self._add_audit(
            task,
            "submission_result_received",
            f"Submission result received for '{task.title}': {result.status.value}",
            {
                "application_id": str(application.id),
                "status": result.status.value,
                "message": result.message,
            },
        )
        await self.session.flush()
        return application

    def _definition_for_task(self, task: Task) -> tuple[WorkflowDefinition, TaskDefinition]:
        workflow = next(
            (
                definition
                for definition in self.workflow_loader.load_all()
                if definition.id == task.workflow_id
            ),
            None,
        )
        if workflow is None:
            raise SubmissionDefinitionError(
                f"No workflow definition found for task workflow '{task.workflow_id}'"
            )
        task_definition = next(
            (definition for definition in workflow.tasks if definition.id == task.task_type),
            None,
        )
        if task_definition is None:
            raise SubmissionDefinitionError(
                f"No task definition '{task.task_type}' in workflow '{task.workflow_id}'"
            )
        return workflow, task_definition

    async def _validate_required_documents(
        self,
        task: Task,
        task_definition: TaskDefinition,
    ) -> None:
        available_types = set(
            (
                await self.session.scalars(
                    select(Document.document_type).where(Document.case_id == task.case_id)
                )
            ).all()
        )
        required_types = {
            requirement.type for requirement in task_definition.required_documents
        }
        missing = sorted(required_types - available_types)
        if missing:
            raise MissingRequiredDocumentsError(missing)

    async def _ensure_no_pending_approval(self, task_id: UUID) -> None:
        existing = await self.session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.task_id == task_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
        )
        if existing is not None:
            raise InvalidApprovalStateError(
                f"Task {task_id} already has pending approval {existing.id}"
            )

    async def _pending_approval(
        self,
        approval_id: UUID,
    ) -> tuple[ApprovalRequest, Task]:
        approval = await self.session.get(ApprovalRequest, approval_id)
        if approval is None:
            raise ApprovalNotFoundError(f"Approval request not found: {approval_id}")
        if approval.status != ApprovalStatus.PENDING:
            raise InvalidApprovalStateError(
                f"Approval request {approval_id} is already {approval.status.value}"
            )
        task = await self.session.get(Task, approval.task_id)
        if task is None:
            raise SubmissionTaskNotFoundError(f"Task not found: {approval.task_id}")
        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise InvalidApprovalStateError(
                f"Task {task.id} is {task.status.value}, not awaiting approval"
            )
        return approval, task

    def _add_audit(
        self,
        task: Task,
        event_type: str,
        description: str,
        details: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEntry(
                case_id=task.case_id,
                task_id=task.id,
                event_type=event_type,
                description=description,
                details=details,
            )
        )
