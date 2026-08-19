"""Workflow activation and deterministic task state transitions."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependency_solver import DependencySolver
from app.core.workflow_loader import WorkflowLoader
from app.core.workflow_schema import WorkflowDefinition
from app.db.base import utc_now
from app.models import AuditEntry, Case, Task, TaskStatus


class WorkflowEngineError(ValueError):
    """Base class for workflow orchestration errors."""


class CaseNotFoundError(WorkflowEngineError):
    """Raised when workflow activation targets a missing case."""


class WorkflowTaskNotFoundError(WorkflowEngineError):
    """Raised when a state transition targets a missing task."""


class WorkflowActivationError(WorkflowEngineError):
    """Raised when applicable workflows cannot form a valid runtime graph."""


class InvalidStateTransitionError(WorkflowEngineError):
    """Raised when a task cannot move directly to the requested state."""

    def __init__(
        self,
        task_id: UUID,
        current_status: TaskStatus,
        attempted_status: TaskStatus,
    ) -> None:
        self.task_id = task_id
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Cannot transition task {task_id} from {current_status.value} "
            f"to {attempted_status.value}"
        )


VALID_TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset(),
    TaskStatus.READY: frozenset(
        {
            TaskStatus.IN_PROGRESS,
            TaskStatus.SUBMITTED,
            TaskStatus.BLOCKED,
        }
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {
            TaskStatus.READY,
            TaskStatus.AWAITING_APPROVAL,
            TaskStatus.SUBMITTED,
            TaskStatus.BLOCKED,
        }
    ),
    TaskStatus.AWAITING_APPROVAL: frozenset(
        {
            TaskStatus.READY,
            TaskStatus.SUBMITTED,
        }
    ),
    TaskStatus.SUBMITTED: frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.READY, TaskStatus.BLOCKED}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.READY}),
}


class WorkflowEngine:
    """Coordinate static workflow definitions with persisted case tasks."""

    def __init__(
        self,
        session: AsyncSession,
        dependency_solver: DependencySolver | None = None,
        workflow_loader: WorkflowLoader | None = None,
    ) -> None:
        self.session = session
        self.dependency_solver = dependency_solver or DependencySolver(session)
        self.workflow_loader = workflow_loader or WorkflowLoader()

    def get_applicable_workflows(
        self,
        profile: Mapping[str, object],
    ) -> list[WorkflowDefinition]:
        """Return definitions whose complete applicability rule set matches."""
        return [
            definition
            for definition in self.workflow_loader.load_all()
            if definition.is_applicable(profile)
        ]

    async def activate_workflows(
        self,
        case_id: UUID,
        profile: Mapping[str, object],
    ) -> list[Task]:
        """Idempotently create applicable tasks and their inter-workflow edges."""
        case = await self.session.get(Case, case_id)
        if case is None:
            raise CaseNotFoundError(f"Case not found: {case_id}")

        definitions = self.get_applicable_workflows(profile)
        definitions_by_id = {definition.id: definition for definition in definitions}
        existing_tasks = list(
            (await self.session.scalars(select(Task).where(Task.case_id == case_id))).all()
        )
        tasks_by_key = {(task.workflow_id, task.task_type): task for task in existing_tasks}

        try:
            for definition in definitions:
                for task_definition in definition.tasks:
                    key = (definition.id, task_definition.id)
                    if key in tasks_by_key:
                        continue
                    task = Task(
                        case_id=case_id,
                        workflow_id=definition.id,
                        task_type=task_definition.id,
                        status=TaskStatus.PENDING,
                        title=task_definition.name,
                    )
                    self.session.add(task)
                    tasks_by_key[key] = task

            await self.session.flush()
            await self._create_inter_workflow_dependencies(
                definitions_by_id,
                tasks_by_key,
            )
            await self._apply_readiness_changes(case_id, context={"reason": "activation"})
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        applicable_ids = set(definitions_by_id)
        return sorted(
            (task for task in tasks_by_key.values() if task.workflow_id in applicable_ids),
            key=lambda task: (task.workflow_id, task.task_type),
        )

    async def transition_task(
        self,
        task_id: UUID,
        new_status: TaskStatus,
        context: Mapping[str, Any] | None = None,
    ) -> Task:
        """Apply one valid transition and any resulting readiness changes atomically."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise WorkflowTaskNotFoundError(f"Task not found: {task_id}")

        current_status = task.status
        if new_status not in VALID_TASK_TRANSITIONS[current_status]:
            raise InvalidStateTransitionError(task_id, current_status, new_status)

        transition_context = dict(context or {})
        try:
            self._set_task_status(task, new_status, transition_context)
            await self.session.flush()
            await self._apply_readiness_changes(
                task.case_id,
                context={"reason": "dependency_evaluation"},
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        return task

    async def _create_inter_workflow_dependencies(
        self,
        definitions_by_id: dict[str, WorkflowDefinition],
        tasks_by_key: dict[tuple[str, str], Task],
    ) -> None:
        for definition in definitions_by_id.values():
            downstream = tasks_by_key[(definition.id, definition.tasks[0].id)]
            for dependency_id in definition.inter_workflow_dependencies:
                dependency_definition = definitions_by_id.get(dependency_id)
                if dependency_definition is None:
                    raise WorkflowActivationError(
                        f"Applicable workflow '{definition.id}' requires inactive workflow "
                        f"'{dependency_id}'"
                    )
                upstream_definition = dependency_definition.tasks[-1]
                upstream = tasks_by_key[(dependency_id, upstream_definition.id)]
                await self.dependency_solver.add_dependency(downstream.id, upstream.id)

    async def _apply_readiness_changes(
        self,
        case_id: UUID,
        *,
        context: Mapping[str, Any],
    ) -> None:
        changes = await self.dependency_solver.evaluate_readiness(case_id)
        if not changes:
            return

        result = await self.session.scalars(select(Task).where(Task.id.in_(changes)))
        tasks = {task.id: task for task in result.all()}
        if set(tasks) != set(changes):
            missing = ", ".join(str(task_id) for task_id in set(changes) - set(tasks))
            raise WorkflowTaskNotFoundError(
                f"Dependency solver returned unknown task IDs: {missing}"
            )
        for task_id, new_status in changes.items():
            self._set_task_status(tasks[task_id], new_status, dict(context))
        await self.session.flush()

    def _set_task_status(
        self,
        task: Task,
        new_status: TaskStatus,
        context: dict[str, Any],
    ) -> None:
        previous_status = task.status
        task.status = new_status
        if new_status == TaskStatus.COMPLETED:
            task.completed_at = utc_now()

        self.session.add(
            AuditEntry(
                case_id=task.case_id,
                task_id=task.id,
                event_type="task_status_changed",
                description=(
                    f"Task '{task.title}' changed from {previous_status.value} "
                    f"to {new_status.value}"
                ),
                details={
                    "transition": {
                        "from": previous_status.value,
                        "to": new_status.value,
                    },
                    "context": context,
                },
            )
        )
