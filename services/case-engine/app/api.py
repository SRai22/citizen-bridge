import hmac
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.benefits import evaluate, readiness
from app.clients import (
    AccessContext,
    AIClient,
    AuthClient,
    AuthorityClient,
    CatalogClient,
    DocumentsClient,
    UserContext,
)
from app.config import settings
from app.db import get_session
from app.kafka import EventPublisher
from app.models import (
    ActiveBenefit,
    ApprovalRequest,
    AuditEntry,
    Case,
    CaseStatus,
    ExternalApplication,
    Task,
    TaskStatus,
)
from app.schemas import (
    CaseCreate,
    CaseCreated,
    CaseDetail,
    CaseListResponse,
    CaseStatusFilter,
    LifeEventCreate,
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
internal_router = APIRouter(prefix="/internal", include_in_schema=False)
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


def documents_client(request: Request) -> DocumentsClient:
    return request.app.state.documents_client


AuthDep = Annotated[AuthClient, Depends(auth_client)]
AuthorityDep = Annotated[AuthorityClient, Depends(authority_client)]
PublisherDep = Annotated[EventPublisher, Depends(publisher)]
CatalogDep = Annotated[CatalogClient, Depends(catalog_client)]
AIDep = Annotated[AIClient, Depends(ai_client)]
DocumentsDep = Annotated[DocumentsClient, Depends(documents_client)]


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


async def _opportunity(
    benefit: dict,
    user: UserContext,
    auth: AuthClient,
    documents: DocumentsClient,
) -> dict:
    profile_response = await auth.profile(user)
    result = evaluate(
        benefit,
        profile_response["profile"],
        profile_response.get("provenance"),
    )
    document_state = await documents.check_requirements(
        user.user_id, benefit.get("required_documents", [])
    )
    return {
        **benefit,
        "eligibility": result,
        "readiness": readiness(benefit, result, document_state),
        "source": "Matched from your saved profile and document wallet",
    }


@router.get("/benefits/active")
async def active_benefits(user: UserDep, session: SessionDep, catalog: CatalogDep) -> dict:
    rows = (
        await session.scalars(
            select(ActiveBenefit)
            .where(ActiveBenefit.user_id == UUID(user.user_id))
            .order_by(ActiveBenefit.started_at.desc())
        )
    ).all()
    definitions = {item["id"]: item for item in await catalog.benefits()}
    return {
        "benefits": [
            {
                "benefit_id": row.benefit_id,
                "name": definitions.get(row.benefit_id, {}).get("name", row.benefit_id),
                "authority": definitions.get(row.benefit_id, {}).get("authority", ""),
                "amount": row.amount,
                "status": row.status,
                "started_at": row.started_at,
                "next_payment_at": row.next_payment_at,
                "case_id": row.source_case_id,
            }
            for row in rows
        ]
    }


@router.get("/benefits/eligible")
async def eligible_benefits(
    user: UserDep, auth: AuthDep, catalog: CatalogDep, documents: DocumentsDep
) -> dict:
    opportunities = [
        await _opportunity(benefit, user, auth, documents) for benefit in await catalog.benefits()
    ]
    return {
        "benefits": [
            item for item in opportunities if item["eligibility"]["status"] != "ineligible"
        ]
    }


@router.get("/benefits/{benefit_id}/readiness")
async def benefit_readiness(
    benefit_id: str,
    user: UserDep,
    auth: AuthDep,
    catalog: CatalogDep,
    documents: DocumentsDep,
) -> dict:
    benefit = await catalog.benefit(benefit_id)
    if benefit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benefit not found")
    return await _opportunity(benefit, user, auth, documents)


@router.post("/benefits/{benefit_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_for_benefit(
    benefit_id: str,
    user: UserDep,
    session: SessionDep,
    auth: AuthDep,
    events: PublisherDep,
    authority: AuthorityDep,
    catalog: CatalogDep,
    documents: DocumentsDep,
) -> dict:
    benefit = await catalog.benefit(benefit_id)
    if benefit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Benefit not found")
    opportunity = await _opportunity(benefit, user, auth, documents)
    if opportunity["eligibility"]["status"] != "eligible":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Eligibility is incomplete")
    if opportunity["readiness"]["percentage"] != 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Application is not ready")
    existing = await session.scalar(
        select(Case.id).where(
            Case.life_event_type == f"benefit_{benefit_id}",
            Case.status.in_([CaseStatus.INTAKE, CaseStatus.ACTIVE]),
            Case.profile["user_id"].as_string() == user.user_id,
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "An application is already active")
    workflow = await catalog.workflow(benefit["workflow_id"])
    payload = CaseCreate(
        life_event=LifeEventCreate(
            type=f"benefit_{benefit_id}",
            context={
                "benefit_id": benefit_id,
                "benefit_name": benefit["name"],
                "benefit_amount": benefit["amount"],
                "user_id": user.user_id,
            },
        )
    )
    try:
        case, decision = await create_case(
            session,
            events,
            authority,
            catalog,
            UUID(user.user_id),
            payload,
            definitions=[workflow],
        )
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return {"case": case_detail(case, decision)}


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


@router.get("/withdrawable")
async def withdrawable(user: UserDep, session: SessionDep, authority: AuthorityDep) -> dict:
    try:
        accessible = await authority.case_access(user.user_id)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    case_ids = [UUID(case_id) for case_id, _ in accessible]
    if not case_ids:
        return {"withdrawable": []}
    rows = (
        await session.scalars(
            select(Task)
            .where(Task.case_id.in_(case_ids))
            .options(selectinload(Task.external_applications))
            .order_by(Task.updated_at.desc())
        )
    ).all()
    return {
        "withdrawable": [
            {
                "task_id": task.id,
                "case_id": task.case_id,
                "title": task.title,
                "authority": application.adapter_type.replace("_", " ").title(),
                "submitted_at": application.created_at,
                "can_withdraw": task.status in {TaskStatus.SUBMITTED, TaskStatus.PENDING},
                "withdrawal_note": "Applications under review may not be withdrawable.",
            }
            for task in rows
            for application in task.external_applications[-1:]
        ]
    }


@router.post("/{case_id}/tasks/{task_id}/withdraw")
async def withdraw_application(
    case_id: UUID,
    task_id: UUID,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> dict:
    await access(authority, user.user_id, case_id, "submit")
    task = await _submission_task(session, case_id, task_id)
    if task.status not in {TaskStatus.SUBMITTED, TaskStatus.PENDING}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This application cannot be withdrawn (already approved/processed)",
        )
    application = task.external_applications[-1] if task.external_applications else None
    if application is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This task has not been submitted")
    previous = task.status
    task.status = TaskStatus.CANCELLED
    application.status = "cancelled"
    session.add(
        AuditEntry(
            case_id=case_id,
            task_id=task_id,
            event_type="application_withdrawn",
            description=f"Withdrawal requested for {task.title}",
            details={"changed_by": user.user_id, "authority": application.adapter_type},
        )
    )
    await session.commit()
    await events.publish(
        "tasks",
        {
            "event_type": "task.status_changed",
            "task_id": str(task.id),
            "case_id": str(case_id),
            "old_status": previous.value,
            "new_status": "cancelled",
            "changed_by": user.user_id,
            "title": task.title,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    authority_name = application.adapter_type.replace("_", " ").title()
    return {
        "withdrawn": True,
        "task_status": "cancelled",
        "note": f"Withdrawal request sent to {authority_name}. Processing may take 1-3 days.",
    }


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
    await access(
        authority,
        user.user_id,
        task.case_id,
        "submit" if settings.demo_mode else "approve",
    )
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
    if settings.demo_mode:
        # DEMO ONLY: simulate the government authority approving immediately after submission so
        # every workflow can be demonstrated end-to-end. Remove this block when real authority
        # status callbacks are connected; production must remain SUBMITTED until that callback.
        application.status = "approved"
        application.response_payload = {
            "message": "Approved automatically for the Citizen Bridge demo."
        }
        await session.commit()
        await transition_task(
            session,
            events,
            task,
            TaskStatus.COMPLETED,
            UUID(user.user_id),
            {"external_reference_id": reference, "demo_auto_approved": True},
        )
        await session.refresh(application)
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
        "responded_at": application.updated_at if application.status == "approved" else None,
    }


@internal_router.get("/users/{user_id}/export")
async def internal_export(
    user_id: UUID,
    session: SessionDep,
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> dict:
    expected = settings.internal_service_token.get_secret_value()
    if not expected or not token or not hmac.compare_digest(token, expected):
        raise _unauthorized("Invalid internal service token")
    ids = list(
        await session.scalars(
            select(Case.id).where(Case.owner_user_id == user_id).order_by(Case.created_at)
        )
    )
    cases = [loaded for case_id in ids if (loaded := await get_case(session, case_id))]
    return {
        "cases": [
            {
                "id": case.id,
                "title": case.title,
                "status": case.status,
                "life_event_type": case.life_event_type,
                "created_at": case.created_at,
                "updated_at": case.updated_at,
                "tasks": [_task_payload(task) for task in case.tasks],
            }
            for case in cases
        ]
    }
