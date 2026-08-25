from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients import (
    AccessContext,
    AIClient,
    AuthClient,
    AuthorityClient,
    CatalogClient,
    UserContext,
)
from app.db import get_session
from app.kafka import EventPublisher
from app.models import ApprovalRequest, ExternalApplication, Task, TaskStatus
from app.schemas import (
    CaseCreate,
    CaseCreated,
    CaseDetail,
    CaseListResponse,
    CaseStatusFilter,
    SetSubjectRequest,
    TaskInputUpdate,
    TaskResponse,
    TaskStageAdvance,
    TaskTransition,
)
from app.service import (
    advance_stage,
    case_detail,
    case_summary,
    create_case,
    get_case,
    list_cases,
    transition_task,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])
approvals_router = APIRouter(prefix="/api/approvals", tags=["approvals"])
bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def auth_client(request: Request) -> AuthClient:
    return request.app.state.auth_client


def authority_client(request: Request) -> AuthorityClient:
    return request.app.state.authority_client


def publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


def catalog_client(request: Request) -> CatalogClient:
    return request.app.state.catalog_client


def ai_client(request: Request) -> AIClient:
    return request.app.state.ai_client


AuthDep = Annotated[AuthClient, Depends(auth_client)]
AuthorityDep = Annotated[AuthorityClient, Depends(authority_client)]
PublisherDep = Annotated[EventPublisher, Depends(publisher)]
CatalogDep = Annotated[CatalogClient, Depends(catalog_client)]
AIDep = Annotated[AIClient, Depends(ai_client)]


async def current_user(credentials: CredentialsDep, auth: AuthDep) -> AsyncIterator[UserContext]:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        user = await auth.validate(credentials.credentials)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if user is None:
        raise _unauthorized("Invalid or expired token")
    context_token = set_user_id(user.user_id)
    try:
        yield user
    finally:
        reset_user_id(context_token)


UserDep = Annotated[UserContext, Depends(current_user)]


async def access(
    authority: AuthorityClient, user_id: str, case_id: UUID, action: str
) -> AccessContext:
    try:
        decision = await authority.check_access(user_id, str(case_id), action)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not decision.allowed:
        allowed = ", ".join(decision.permissions) or "no actions"
        role = decision.role or "current role"
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"As {role}, you can: {allowed}. '{action}' requires additional authority.",
        )
    return decision


@router.post("", response_model=CaseCreated, status_code=status.HTTP_201_CREATED)
async def create(
    payload: CaseCreate,
    user: UserDep,
    session: SessionDep,
    events: PublisherDep,
    authority: AuthorityDep,
    catalog: CatalogDep,
) -> CaseDetail:
    try:
        case, decision = await create_case(
            session, events, authority, catalog, UUID(user.user_id), payload
        )
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return case_detail(case, decision)


@router.get("", response_model=CaseListResponse)
async def index(
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    status_filter: Annotated[CaseStatusFilter | None, Query(alias="status")] = None,
    life_event_type: str | None = None,
) -> CaseListResponse:
    try:
        accessible = await authority.case_access(user.user_id)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    roles = {UUID(case_id): role for case_id, role in accessible}
    cases = await list_cases(session, list(roles))
    return CaseListResponse(
        cases=[
            case_summary(case, roles[case.id])
            for case in cases
            if (status_filter is None or case.status.value == status_filter)
            and (life_event_type is None or case.life_event_type == life_event_type)
        ]
    )


@router.get("/context/for-whom")
async def for_whom(
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> dict:
    try:
        accessible = await authority.case_access(user.user_id)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    case_ids = [UUID(case_id) for case_id, _ in accessible]
    cases = await list_cases(session, case_ids)
    members = [
        person
        for case in cases
        if case.household_profile
        for person in case.household_profile.people
    ]
    unique = {member.id: member for member in members}
    return {
        "options": [
            {"type": "self", "user_id": user.user_id},
            {
                "type": "family",
                "members": [
                    {
                        "person_id": str(member.id),
                        "name": member.name,
                        "relationship": member.relationship,
                    }
                    for member in unique.values()
                ],
            },
            {"type": "other", "requires": "relationship_description"},
        ]
    }


@router.post("/context/set-subject", response_model=CaseDetail)
async def set_subject(
    payload: SetSubjectRequest,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> CaseDetail:
    await access(authority, user.user_id, payload.case_id, "manage")
    case = await get_case(session, payload.case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    members = case.household_profile.people if case.household_profile else []
    if not any(person.id == payload.subject_person_id for person in members):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Subject is not in this case")
    case.subject_person_id = payload.subject_person_id
    case.coordinator_user_id = UUID(user.user_id)
    case.subject_relationship = payload.relationship
    await session.commit()
    decision = await authority.register_coordinator(
        user.user_id,
        str(case.id),
        str(payload.subject_person_id),
        payload.relationship,
    )
    return case_detail(case, decision)


@router.get("/{case_id}", response_model=CaseDetail)
async def detail(
    case_id: UUID, user: UserDep, session: SessionDep, authority: AuthorityDep
) -> CaseDetail:
    decision = await access(authority, user.user_id, case_id, "view")
    case = await get_case(session, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case_detail(case, decision)


@router.get("/{case_id}/tasks/{task_id}", response_model=TaskResponse)
async def task_detail(
    case_id: UUID,
    task_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> TaskResponse:
    decision = await access(authority, user.user_id, case_id, "view")
    case = await get_case(session, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    groups = case_detail(case, decision).tasks_by_group
    tasks = groups.ready + groups.waiting + groups.blocked + groups.completed
    result = next((task for task in tasks if task.task_id == task_id), None)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return result


@router.get("/{case_id}/tasks/{task_id}/detail")
async def full_task_detail(
    case_id: UUID,
    task_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> dict:
    await access(authority, user.user_id, case_id, "view")
    task = await _submission_task(session, case_id, task_id)
    return _task_payload(task)


@router.get("/{case_id}/tasks/{task_id}/requirements")
async def task_requirements(
    case_id: UUID,
    task_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> list:
    await access(authority, user.user_id, case_id, "view")
    await _submission_task(session, case_id, task_id)
    return []


@router.patch("/{case_id}/tasks/{task_id}/detail")
async def update_task_input(
    case_id: UUID,
    task_id: UUID,
    payload: TaskInputUpdate,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
) -> dict:
    await access(authority, user.user_id, case_id, "submit")
    task = await _submission_task(session, case_id, task_id)
    if task.status not in {TaskStatus.READY, TaskStatus.IN_PROGRESS}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task is not editable")
    task.input_data = payload.input_data
    await session.commit()
    return _task_payload(task)


@router.post("/{case_id}/tasks/{task_id}/prepare")
async def prepare_submission(
    case_id: UUID,
    task_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> dict:
    await access(authority, user.user_id, case_id, "submit")
    task = await _submission_task(session, case_id, task_id)
    if task.status not in {TaskStatus.READY, TaskStatus.IN_PROGRESS}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Task is not ready for submission")
    pending = next((item for item in task.approval_requests if item.status == "pending"), None)
    if pending:
        return _approval_payload(pending)
    if task.status == TaskStatus.READY:
        await transition_task(session, events, task, TaskStatus.IN_PROGRESS, UUID(user.user_id), {})
    approval = ApprovalRequest(
        task_id=task.id,
        action_description=f"Submit {task.title} to the responsible government authority",
        context={"input_data": dict(task.input_data), "required_documents": []},
    )
    session.add(approval)
    await session.commit()
    await session.refresh(approval)
    await transition_task(
        session, events, task, TaskStatus.AWAITING_APPROVAL, UUID(user.user_id), {}
    )
    return _approval_payload(approval)


@approvals_router.post("/{approval_id}/approve")
async def approve_submission(
    approval_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> dict:
    approval = await session.get(ApprovalRequest, approval_id)
    if approval is None or approval.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pending approval not found")
    task = await session.get(Task, approval.task_id)
    assert task is not None
    await session.refresh(task, attribute_names=["wait_state"])
    await access(authority, user.user_id, task.case_id, "approve")
    approval.status = "approved"
    reference = f"CB/{task.workflow_id.upper()}/{datetime.now(UTC).year}/{uuid4().hex[:8].upper()}"
    application = ExternalApplication(
        task_id=task.id,
        adapter_type=task.workflow_id,
        external_reference_id=reference,
        status="submitted",
        request_payload=dict(task.input_data),
        response_payload={"message": "Submission accepted for processing"},
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    await transition_task(
        session,
        events,
        task,
        TaskStatus.SUBMITTED,
        UUID(user.user_id),
        {"external_reference_id": reference},
    )
    return _application_payload(application)


@approvals_router.post("/{approval_id}/reject")
async def reject_submission(
    approval_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> dict:
    approval = await session.get(ApprovalRequest, approval_id)
    if approval is None or approval.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pending approval not found")
    task = await session.get(Task, approval.task_id)
    assert task is not None
    await session.refresh(task, attribute_names=["wait_state"])
    await access(authority, user.user_id, task.case_id, "submit")
    approval.status = "rejected"
    await session.commit()
    await transition_task(session, events, task, TaskStatus.READY, UUID(user.user_id), {})
    return _approval_payload(approval)


@router.post("/{case_id}/tasks/{task_id}/transition", response_model=TaskResponse)
async def transition(
    case_id: UUID,
    task_id: UUID,
    payload: TaskTransition,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
    ai: AIDep,
) -> TaskResponse:
    decision = await access(authority, user.user_id, case_id, "submit")
    task = await session.scalar(
        select(Task).where(Task.id == task_id).options(selectinload(Task.wait_state))
    )
    if task is None or task.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    if task.status.value == "awaiting_approval" and payload.status.value == "submitted":
        decision = await access(authority, user.user_id, case_id, "approve")
    output_data = dict(payload.output_data)
    rejection_text = output_data.get("rejection_text")
    if payload.status.value == "failed" and isinstance(rejection_text, str):
        try:
            output_data["rejection_interpretation"] = await ai.interpret_rejection(
                str(task.id), rejection_text
            )
        except ConnectionError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    try:
        await transition_task(
            session, events, task, payload.status, UUID(user.user_id), output_data
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    case = await get_case(session, case_id)
    assert case is not None
    groups = case_detail(case, decision).tasks_by_group
    return next(
        item
        for item in groups.ready + groups.waiting + groups.blocked + groups.completed
        if item.task_id == task_id
    )


@router.post("/{case_id}/tasks/{task_id}/stage", response_model=TaskResponse)
async def stage(
    case_id: UUID,
    task_id: UUID,
    payload: TaskStageAdvance,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> TaskResponse:
    decision = await access(authority, user.user_id, case_id, "submit")
    task = await session.scalar(
        select(Task).where(Task.id == task_id).options(selectinload(Task.wait_state))
    )
    if task is None or task.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    try:
        await advance_stage(session, events, task, payload.stage, UUID(user.user_id))
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    case = await get_case(session, case_id)
    assert case is not None
    groups = case_detail(case, decision).tasks_by_group
    return next(
        item
        for item in groups.ready + groups.waiting + groups.blocked + groups.completed
        if item.task_id == task_id
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _submission_task(session: AsyncSession, case_id: UUID, task_id: UUID) -> Task:
    task = await session.scalar(
        select(Task)
        .where(Task.id == task_id, Task.case_id == case_id)
        .options(
            selectinload(Task.dependencies),
            selectinload(Task.approval_requests),
            selectinload(Task.external_applications),
            selectinload(Task.wait_state),
        )
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return task


def _task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "case_id": task.case_id,
        "workflow_id": task.workflow_id,
        "task_type": task.task_type,
        "status": task.status,
        "title": task.title,
        "description": task.description,
        "input_data": task.input_data,
        "output_data": task.output_data,
        "completed_at": task.completed_at,
        "dependencies": [
            {
                "id": item.id,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "task_id": item.task_id,
                "depends_on_task_id": item.depends_on_task_id,
                "dependency_type": item.dependency_type,
            }
            for item in task.dependencies
        ],
        "external_applications": [
            _application_payload(item) for item in task.external_applications
        ],
        "approval_requests": [_approval_payload(item) for item in task.approval_requests],
        "required_documents": [],
        "produced_documents": [],
    }


def _approval_payload(approval: ApprovalRequest) -> dict:
    return {
        "id": approval.id,
        "created_at": approval.created_at,
        "updated_at": approval.updated_at,
        "task_id": approval.task_id,
        "action_description": approval.action_description,
        "status": approval.status,
        "context": approval.context,
        "requested_at": approval.created_at,
        "resolved_at": approval.updated_at if approval.status != "pending" else None,
    }


def _application_payload(application: ExternalApplication) -> dict:
    return {
        "id": application.id,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "task_id": application.task_id,
        "adapter_type": application.adapter_type,
        "external_reference_id": application.external_reference_id,
        "status": application.status,
        "request_payload": application.request_payload,
        "response_payload": application.response_payload,
        "submitted_at": application.created_at,
        "responded_at": None,
    }
