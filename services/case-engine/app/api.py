from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import AccessContext, AuthClient, AuthorityClient, CatalogClient, UserContext
from app.db import get_session
from app.kafka import EventPublisher
from app.models import Task
from app.schemas import (
    CaseCreate,
    CaseCreated,
    CaseDetail,
    CaseListResponse,
    CaseStatusFilter,
    TaskResponse,
    TaskTransition,
)
from app.service import (
    case_detail,
    case_summary,
    create_case,
    get_case,
    list_cases,
    transition_task,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])
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


AuthDep = Annotated[AuthClient, Depends(auth_client)]
AuthorityDep = Annotated[AuthorityClient, Depends(authority_client)]
PublisherDep = Annotated[EventPublisher, Depends(publisher)]
CatalogDep = Annotated[CatalogClient, Depends(catalog_client)]


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
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{action.title()} access required")
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


@router.post("/{case_id}/tasks/{task_id}/transition", response_model=TaskResponse)
async def transition(
    case_id: UUID,
    task_id: UUID,
    payload: TaskTransition,
    user: UserDep,
    session: SessionDep,
    authority: AuthorityDep,
    events: PublisherDep,
) -> TaskResponse:
    decision = await access(authority, user.user_id, case_id, "submit")
    task = await session.get(Task, task_id)
    if task is None or task.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    try:
        await transition_task(
            session, events, task, payload.status, UUID(user.user_id), payload.output_data
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


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
