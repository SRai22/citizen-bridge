from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_client import AuthClient
from app.db import get_session
from app.kafka import EventPublisher
from app.provider import AIProvider, AIUnavailableError
from app.schemas import (
    ConfirmedProfileResponse,
    ConfirmIntakeRequest,
    ConversationResponse,
    IntakeMessageRequest,
    InterpretationResponse,
    RejectionRequest,
    StartIntakeRequest,
)
from app.service import confirm_intake, interpret_rejection, send_intake_message, start_intake

router = APIRouter(prefix="/api/ai", tags=["ai"])
bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def auth_client(request: Request) -> AuthClient:
    return request.app.state.auth_client


def publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


def provider(request: Request) -> AIProvider:
    return request.app.state.provider


AuthDep = Annotated[AuthClient, Depends(auth_client)]
PublisherDep = Annotated[EventPublisher, Depends(publisher)]
ProviderDep = Annotated[AIProvider, Depends(provider)]


async def current_user(credentials: CredentialsDep, auth: AuthDep) -> AsyncIterator[UUID]:
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
    token = set_user_id(str(user_id))
    try:
        yield user_id
    finally:
        reset_user_id(token)


UserDep = Annotated[UUID, Depends(current_user)]


@router.post(
    "/intake/start", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def start(
    payload: StartIntakeRequest,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
    ai: ProviderDep,
) -> ConversationResponse:
    model = "mock" if ai.settings.ai_mock_mode else ai.settings.intake_model
    return await start_intake(session, events, user_id, payload.category_id, model)


@router.post("/intake/{conversation_id}/message", response_model=ConversationResponse)
async def intake_message(
    conversation_id: UUID,
    payload: IntakeMessageRequest,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
    ai: ProviderDep,
) -> ConversationResponse:
    try:
        return await send_intake_message(
            session, events, ai, conversation_id, payload.message, user_id
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AIUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc


@router.post("/intake/{conversation_id}/confirm", response_model=ConfirmedProfileResponse)
async def confirm(
    conversation_id: UUID,
    payload: ConfirmIntakeRequest,
    user_id: UserDep,
    session: SessionDep,
    events: PublisherDep,
) -> ConfirmedProfileResponse:
    try:
        profile = await confirm_intake(
            session, events, conversation_id, user_id, payload.profile_confirmed
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return ConfirmedProfileResponse(profile=profile)


@router.post("/interpret-rejection", response_model=InterpretationResponse)
async def rejection(
    payload: RejectionRequest,
    _: UserDep,
    session: SessionDep,
    ai: ProviderDep,
) -> InterpretationResponse:
    try:
        result = await interpret_rejection(
            session, ai, payload.rejection_text, payload.task_type, payload.context
        )
    except AIUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return InterpretationResponse(
        interpretation=result.explanation,
        cause=result.cause,
        confidence=result.confidence,
        remediation_actions=[result.remediation],
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
