from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients import AccessContext, AuthorityClient
from app.models import (
    AuditEntry,
    Case,
    CaseStatus,
    HouseholdProfile,
    LifeEvent,
    Person,
    Task,
    TaskDependency,
    TaskStatus,
)
from app.schemas import (
    CaseCreate,
    CaseDetail,
    CaseSummary,
    Progress,
    SubjectResponse,
    TaskGroups,
    TaskResponse,
    WaitState,
)


class Publisher(Protocol):
    async def publish(self, topic: str, event: dict[str, Any]) -> None: ...


class WorkflowCatalog(Protocol):
    async def list_applicable(self, profile: dict[str, object]) -> list[dict]: ...


VALID_TRANSITIONS = {
    TaskStatus.PENDING: set(),
    TaskStatus.READY: {TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED, TaskStatus.BLOCKED},
    TaskStatus.IN_PROGRESS: {
        TaskStatus.READY,
        TaskStatus.AWAITING_APPROVAL,
        TaskStatus.SUBMITTED,
        TaskStatus.BLOCKED,
    },
    TaskStatus.AWAITING_APPROVAL: {TaskStatus.READY, TaskStatus.SUBMITTED},
    TaskStatus.SUBMITTED: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.READY, TaskStatus.BLOCKED},
    TaskStatus.BLOCKED: {TaskStatus.READY},
}


async def create_case(
    session: AsyncSession,
    publisher: Publisher,
    authority: AuthorityClient,
    catalog: WorkflowCatalog,
    user_id: UUID,
    payload: CaseCreate,
) -> tuple[Case, AccessContext]:
    event = payload.life_event
    household = None
    if payload.household_profile:
        household = HouseholdProfile(
            location_city=payload.household_profile.location_city,
            location_state=payload.household_profile.location_state,
            people=[Person(**person.model_dump()) for person in payload.household_profile.people],
        )
    case = Case(
        title=f"{event.type.replace('_', ' ').title()} — Administrative Formalities",
        status=CaseStatus.ACTIVE,
        life_event_type=event.type,
        profile=event.context,
        life_event=LifeEvent(
            event_type=event.type,
            context=event.context,
            **({"occurred_at": event.occurred_at} if event.occurred_at else {}),
        ),
        household_profile=household,
    )
    session.add(case)
    await session.flush()

    definitions = await catalog.list_applicable(event.context)
    tasks_by_workflow: dict[str, Task] = {}
    for definition in definitions:
        task_definition = definition["tasks"][0]
        task = Task(
            case_id=case.id,
            workflow_id=definition["id"],
            task_type=task_definition["id"],
            title=task_definition["name"],
            description=definition["description"],
            estimated_duration_days=task_definition["estimated_duration_days"],
            status=TaskStatus.PENDING,
        )
        session.add(task)
        tasks_by_workflow[definition["id"]] = task
    await session.flush()

    dependent_ids: set[UUID] = set()
    for definition in definitions:
        task = tasks_by_workflow[definition["id"]]
        for prerequisite_id in definition["inter_workflow_dependencies"]:
            prerequisite = tasks_by_workflow[prerequisite_id]
            session.add(TaskDependency(task_id=task.id, depends_on_task_id=prerequisite.id))
            dependent_ids.add(task.id)
    for task in tasks_by_workflow.values():
        task.status = TaskStatus.PENDING if task.id in dependent_ids else TaskStatus.READY
    session.add(
        AuditEntry(
            case_id=case.id,
            event_type="case_created",
            description=f"Case '{case.title}' created",
            details={"user_id": str(user_id)},
        )
    )
    await session.commit()

    try:
        access = await authority.register_owner(str(user_id), str(case.id))
    except Exception:
        await session.delete(case)
        await session.commit()
        raise

    # ponytail: direct publish is MVP-only; use a transactional outbox when delivery is guaranteed.
    await publisher.publish(
        "cases",
        _event(
            "case.created",
            case_id=str(case.id),
            user_id=str(user_id),
            status=case.status.value,
            life_event_type=case.life_event_type,
        ),
    )
    for task in tasks_by_workflow.values():
        await publisher.publish(
            "tasks",
            _event(
                "task.created",
                task_id=str(task.id),
                case_id=str(case.id),
                task_type=task.task_type,
                title=task.title,
                new_status=task.status.value,
            ),
        )
    loaded = await get_case(session, case.id)
    if loaded is None:
        raise RuntimeError("Created case disappeared")
    return loaded, access


async def get_case(session: AsyncSession, case_id: UUID) -> Case | None:
    return await session.scalar(
        select(Case)
        .where(Case.id == case_id)
        .options(
            selectinload(Case.life_event),
            selectinload(Case.household_profile).selectinload(HouseholdProfile.people),
            selectinload(Case.tasks).selectinload(Task.dependencies),
        )
    )


async def list_cases(session: AsyncSession, case_ids: list[UUID]) -> list[Case]:
    if not case_ids:
        return []
    result = await session.scalars(
        select(Case)
        .where(Case.id.in_(case_ids))
        .options(selectinload(Case.tasks))
        .order_by(Case.updated_at.desc())
    )
    return list(result.unique().all())


async def transition_task(
    session: AsyncSession,
    publisher: Publisher,
    task: Task,
    status: TaskStatus,
    user_id: UUID,
    output_data: dict[str, Any],
) -> Task:
    previous = task.status
    if status not in VALID_TRANSITIONS[previous]:
        raise ValueError(f"Cannot transition task from {previous.value} to {status.value}")
    task.status = status
    if output_data:
        task.output_data.update(output_data)
    if status == TaskStatus.COMPLETED:
        task.completed_at = datetime.now(UTC)
    session.add(
        AuditEntry(
            case_id=task.case_id,
            task_id=task.id,
            event_type="task_status_changed",
            description=f"Task changed from {previous.value} to {status.value}",
            details={"changed_by": str(user_id)},
        )
    )
    await session.commit()
    event_type = (
        "task.completed"
        if status == TaskStatus.COMPLETED
        else "task.failed"
        if status == TaskStatus.FAILED
        else "task.status_changed"
    )
    await publisher.publish(
        "tasks",
        _event(
            event_type,
            task_id=str(task.id),
            case_id=str(task.case_id),
            old_status=previous.value,
            new_status=status.value,
            changed_by=str(user_id),
            owner_user_id=str(user_id),
            task_type=task.task_type,
            title=task.title,
            output_data=output_data,
        ),
    )
    return task


def case_summary(case: Case, role: str) -> CaseSummary:
    completed = sum(task.status == TaskStatus.COMPLETED for task in case.tasks)
    return CaseSummary(
        case_id=case.id,
        title=case.title,
        status=case.status,
        life_event_type=case.life_event_type,
        my_role=role,
        progress=Progress(completed=completed, total=len(case.tasks)),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def case_detail(case: Case, access: AccessContext) -> CaseDetail:
    groups = TaskGroups()
    task_by_id = {task.id: task for task in case.tasks}
    for task in sorted(case.tasks, key=lambda item: (item.workflow_id, item.title)):
        blocked_by = [
            dependency.depends_on_task_id
            for dependency in task.dependencies
            if task_by_id[dependency.depends_on_task_id].status != TaskStatus.COMPLETED
        ]
        response = TaskResponse(
            task_id=task.id,
            case_id=case.id,
            workflow_id=task.workflow_id,
            task_type=task.task_type,
            title=task.title,
            description=task.description,
            status=task.status,
            completed_at=task.completed_at,
            blocked_reason=("Waiting for prerequisite tasks" if blocked_by else None),
            blocked_by_task_ids=blocked_by,
            wait_state=(
                WaitState(
                    status_label="Processing",
                    estimated_wait={"min_days": 1, "max_days": task.estimated_duration_days},
                    last_update=task.updated_at,
                    is_overdue=False,
                    message="We'll notify you when there's an update.",
                )
                if task.status in {TaskStatus.SUBMITTED, TaskStatus.AWAITING_APPROVAL}
                else None
            ),
        )
        if task.status == TaskStatus.COMPLETED:
            groups.completed.append(response)
        elif task.status in {TaskStatus.SUBMITTED, TaskStatus.AWAITING_APPROVAL}:
            groups.waiting.append(response)
        elif task.status in {TaskStatus.PENDING, TaskStatus.BLOCKED}:
            groups.blocked.append(response)
        else:
            groups.ready.append(response)

    deceased = next(
        (
            person
            for person in (case.household_profile.people if case.household_profile else [])
            if person.is_deceased
        ),
        None,
    )
    summary = case_summary(case, access.role)
    return CaseDetail(
        **summary.model_dump(),
        my_permissions=access.permissions,
        subject=(
            SubjectResponse(
                person_id=deceased.id,
                name=deceased.name,
                relationship=deceased.relationship,
            )
            if deceased
            else None
        ),
        tasks_by_group=groups,
        life_event={
            "event_type": case.life_event.event_type,
            "occurred_at": case.life_event.occurred_at,
        },
    )


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {"event_type": event_type, "timestamp": datetime.now(UTC).isoformat(), **fields}
