from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients import AccessContext, AuthorityClient
from app.models import (
    ActiveBenefit,
    AuditEntry,
    Case,
    CaseStatus,
    HouseholdProfile,
    LifeEvent,
    Person,
    Task,
    TaskDependency,
    TaskStatus,
    TaskWaitState,
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
    definitions: list[dict] | None = None,
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

    definitions = (
        definitions if definitions is not None else await catalog.list_applicable(event.context)
    )
    tasks_by_workflow: dict[str, Task] = {}
    for definition in definitions:
        task_definition = definition["tasks"][0]
        duration = definition.get("typical_duration_days") or (
            1,
            task_definition["estimated_duration_days"],
        )
        task = Task(
            case_id=case.id,
            workflow_id=definition["id"],
            task_type=task_definition["id"],
            title=task_definition["name"],
            description=definition["description"],
            estimated_duration_days=task_definition["estimated_duration_days"],
            status=TaskStatus.PENDING,
            wait_state=TaskWaitState(
                stages_known=bool(definition.get("stages")),
                stages=definition.get("stages", []),
                estimated_wait_days_min=duration[0],
                estimated_wait_days_max=duration[1],
            ),
        )
        session.add(task)
        tasks_by_workflow[definition["id"]] = task
    await session.flush()

    if payload.subject_person_index is not None:
        if household is None or payload.subject_person_index >= len(household.people):
            raise ValueError("subject_person_index does not identify a household member")
        subject = household.people[payload.subject_person_index]
        case.subject_person_id = subject.id
        case.coordinator_user_id = user_id
        case.subject_relationship = payload.subject_relationship or subject.relationship

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
        access = (
            await authority.register_coordinator(
                str(user_id),
                str(case.id),
                str(case.subject_person_id),
                case.subject_relationship or "",
            )
            if case.coordinator_user_id
            else await authority.register_owner(str(user_id), str(case.id))
        )
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
            selectinload(Case.tasks).selectinload(Task.wait_state),
        )
    )


async def list_cases(session: AsyncSession, case_ids: list[UUID]) -> list[Case]:
    if not case_ids:
        return []
    result = await session.scalars(
        select(Case)
        .where(Case.id.in_(case_ids))
        .options(
            selectinload(Case.tasks),
            selectinload(Case.household_profile).selectinload(HouseholdProfile.people),
        )
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
    wait = task.wait_state
    now = datetime.now(UTC)
    if wait:
        wait.last_status_update_at = now
        if status == TaskStatus.SUBMITTED:
            wait.submitted_at = wait.submitted_at or now
            wait.current_stage = wait.current_stage or (
                str(wait.stages[0]["id"]) if wait.stages else "submitted"
            )
            wait.stage_entered_at = now
    session.add(
        AuditEntry(
            case_id=task.case_id,
            task_id=task.id,
            event_type="task_status_changed",
            description=f"Task changed from {previous.value} to {status.value}",
            details={"changed_by": str(user_id)},
        )
    )
    completed_case: Case | None = None
    if status == TaskStatus.COMPLETED:
        await session.flush()
        unfinished = await session.scalar(
            select(Task.id).where(
                Task.case_id == task.case_id,
                Task.id != task.id,
                Task.status != TaskStatus.COMPLETED,
            )
        )
        case = await session.get(Case, task.case_id)
        if unfinished is None and case is not None:
            case.status = CaseStatus.COMPLETED
            completed_case = case
            benefit_id = case.profile.get("benefit_id")
            owner_id = case.profile.get("user_id")
            if benefit_id and owner_id:
                session.add(
                    ActiveBenefit(
                        user_id=UUID(str(owner_id)),
                        benefit_id=str(benefit_id),
                        source_case_id=case.id,
                        amount=str(case.profile.get("benefit_amount", "")),
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
    if completed_case is not None:
        await publisher.publish(
            "cases",
            _event(
                "case.completed",
                case_id=str(completed_case.id),
                user_id=str(completed_case.profile.get("user_id") or user_id),
                benefit_id=completed_case.profile.get("benefit_id"),
                status=completed_case.status.value,
            ),
        )
    return task


async def advance_stage(
    session: AsyncSession,
    publisher: Publisher,
    task: Task,
    stage: str,
    user_id: UUID,
) -> TaskWaitState:
    wait = task.wait_state
    if wait is None or not wait.stages_known:
        raise ValueError("This workflow does not expose processing stages")
    stage_ids = [str(item["id"]) for item in wait.stages]
    if stage not in stage_ids:
        raise ValueError("Unknown workflow stage")
    if wait.current_stage and stage_ids.index(stage) < stage_ids.index(wait.current_stage):
        raise ValueError("Cannot move a task to an earlier stage")
    now = datetime.now(UTC)
    wait.current_stage = stage
    wait.stage_entered_at = now
    wait.last_status_update_at = now
    await session.commit()
    await publisher.publish(
        "tasks",
        _event(
            "task.stage_advanced",
            task_id=str(task.id),
            case_id=str(task.case_id),
            new_stage=stage,
            changed_by=str(user_id),
            new_status=task.status.value,
        ),
    )
    return wait


async def mark_overdue_tasks(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    waits = (
        await session.scalars(
            select(TaskWaitState).where(
                TaskWaitState.submitted_at.is_not(None),
                TaskWaitState.estimated_wait_days_max.is_not(None),
                TaskWaitState.is_overdue.is_(False),
            )
        )
    ).all()
    overdue = [
        wait
        for wait in waits
        if wait.submitted_at
        and wait.estimated_wait_days_max is not None
        and wait.submitted_at + timedelta(days=wait.estimated_wait_days_max) < now
    ]
    for wait in overdue:
        wait.is_overdue = True
    if overdue:
        await session.commit()
    return len(overdue)


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
        wait_state = _wait_state(task)
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
            wait_state=wait_state,
            wait_summary=_wait_summary(wait_state),
        )
        if task.status == TaskStatus.COMPLETED:
            groups.completed.append(response)
        elif task.status in {TaskStatus.SUBMITTED, TaskStatus.AWAITING_APPROVAL}:
            groups.waiting.append(response)
        elif task.status in {TaskStatus.PENDING, TaskStatus.BLOCKED}:
            groups.blocked.append(response)
        else:
            groups.ready.append(response)

    subject = next(
        (
            person
            for person in (case.household_profile.people if case.household_profile else [])
            if person.id == case.subject_person_id
        ),
        None,
    )
    if subject is None and case.subject_person_id is None:
        subject = next(
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
        limitations=access.limitations,
        subject=(
            SubjectResponse(
                person_id=subject.id,
                name=subject.name,
                relationship=case.subject_relationship or subject.relationship,
            )
            if subject
            else None
        ),
        tasks_by_group=groups,
        life_event={
            "event_type": case.life_event.event_type,
            "occurred_at": case.life_event.occurred_at,
        },
    )


def _wait_state(task: Task) -> WaitState | None:
    wait = task.wait_state
    if wait is None or task.status not in {
        TaskStatus.PENDING,
        TaskStatus.SUBMITTED,
        TaskStatus.AWAITING_APPROVAL,
    }:
        return None
    stage_ids = [str(item["id"]) for item in wait.stages]
    current = stage_ids.index(wait.current_stage) if wait.current_stage in stage_ids else -1
    stages = [
        {
            **stage,
            "completed": index < current,
            "current": index == current,
        }
        for index, stage in enumerate(wait.stages)
    ]
    return WaitState(
        stages_known=wait.stages_known,
        stages=stages,
        current_stage=wait.current_stage,
        status_label=None if wait.stages_known else "Processing",
        submitted_at=wait.submitted_at,
        estimated_wait={
            "min_days": wait.estimated_wait_days_min,
            "max_days": wait.estimated_wait_days_max,
        },
        last_update=wait.last_status_update_at or task.updated_at,
        is_overdue=wait.is_overdue,
        message=None if wait.stages_known else "We'll notify you when there's an update.",
    )


def _wait_summary(wait: WaitState | None) -> str | None:
    if wait is None:
        return None
    stage = wait.current_stage.replace("_", " ").title() if wait.current_stage else "Waiting"
    minimum = wait.estimated_wait.get("min_days")
    maximum = wait.estimated_wait.get("max_days")
    estimate = f"~{minimum}-{maximum} days" if minimum is not None and maximum else "ETA unknown"
    return f"{stage} · {estimate} · Last update: {wait.last_update.date().isoformat()}"


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {"event_type": event_type, "timestamp": datetime.now(UTC).isoformat(), **fields}
