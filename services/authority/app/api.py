from collections.abc import AsyncIterator
from typing import Annotated, Literal
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_client import AuthClient
from app.db import get_session
from app.kafka import EventPublisher
from app.models import AuthorityGrant, Delegation
from app.schemas import (
    AccessResponse,
    Action,
    CaseAccessList,
    CaseAccessResponse,
    DelegationRequest,
    DelegationResponse,
    GrantRequest,
    GrantResponse,
    ResourceType,
    RevokeRequest,
)
from app.service import (
    check_access,
    create_delegation,
    create_grant,
    list_user_cases,
    revoke_delegation,
    revoke_grant,
)

router = APIRouter(prefix="/api/authority", tags=["authority"])
bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_auth_client(request: Request) -> AuthClient:
    return request.app.state.auth_client


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


AuthClientDep = Annotated[AuthClient, Depends(get_auth_client)]
PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]


async def current_user_id(credentials: CredentialsDep, auth: AuthClientDep) -> AsyncIterator[UUID]:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        validation = await auth.validate(credentials.credentials)
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not validation.valid:
        raise _unauthorized("Invalid or expired token")
    try:
        user_id = UUID(validation.user_id)
    except ValueError as exc:
        raise _unauthorized("Invalid token subject") from exc
    context_token = set_user_id(str(user_id))
    try:
        yield user_id
    finally:
        reset_user_id(context_token)


CurrentUserDep = Annotated[UUID, Depends(current_user_id)]


@router.get("/check", response_model=AccessResponse)
async def check(
    user_id: UUID,
    resource_type: ResourceType,
    resource_id: UUID,
    action: Action,
    caller_id: CurrentUserDep,
    session: SessionDep,
) -> AccessResponse:
    if caller_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot inspect another user's access")
    return AccessResponse.model_validate(
        await check_access(session, user_id, resource_type, resource_id, action),
        from_attributes=True,
    )


@router.get("/cases", response_model=CaseAccessList)
async def cases(user_id: CurrentUserDep, session: SessionDep) -> CaseAccessList:
    rows = await list_user_cases(session, user_id)
    return CaseAccessList(
        cases=[
            CaseAccessResponse(case_id=case_id, role=role, granted_at=granted_at)
            for case_id, role, granted_at in rows
        ]
    )


@router.post("/grants", response_model=GrantResponse, status_code=status.HTTP_201_CREATED)
async def grant(
    payload: GrantRequest,
    actor_id: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
    auth: AuthClientDep,
) -> AuthorityGrant:
    try:
        if not await auth.user_exists(str(payload.grantee_id)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Grantee not found")
        return await create_grant(
            session,
            publisher,
            actor_id,
            payload.grantee_id,
            payload.resource_type,
            payload.resource_id,
            payload.role,
            payload.expires_at,
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    grant_id: UUID,
    payload: RevokeRequest,
    actor_id: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> Response:
    grant = await session.get(AuthorityGrant, grant_id)
    if grant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    try:
        await revoke_grant(session, publisher, actor_id, grant, payload.reason)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/delegations", response_model=DelegationResponse, status_code=status.HTTP_201_CREATED)
async def delegate(
    payload: DelegationRequest,
    delegator_id: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
    auth: AuthClientDep,
) -> Delegation:
    try:
        if not await auth.user_exists(str(payload.delegate_id)):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Delegate not found")
        return await create_delegation(
            session,
            publisher,
            delegator_id,
            payload.delegate_id,
            payload.scope_type,
            payload.scope_id,
            payload.role,
            list(payload.permissions),
            payload.valid_until,
        )
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.get("/delegations", response_model=list[DelegationResponse])
async def delegations(
    user_id: CurrentUserDep,
    session: SessionDep,
    direction: Literal["given", "received"] = Query(),
) -> list[Delegation]:
    field = Delegation.delegator_id if direction == "given" else Delegation.delegate_id
    return list(await session.scalars(select(Delegation).where(field == user_id)))


@router.delete("/delegations/{delegation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_delegation_endpoint(
    delegation_id: UUID,
    actor_id: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> Response:
    delegation = await session.get(Delegation, delegation_id)
    if delegation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Delegation not found")
    try:
        await revoke_delegation(session, publisher, actor_id, delegation)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
