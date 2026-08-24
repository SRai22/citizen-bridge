import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.kafka import EventPublisher
from app.models import RefreshToken, User
from app.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegistrationRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)
from app.security import (
    InvalidTokenError,
    LoginRateLimiter,
    TokenManager,
    hash_password,
    token_digest,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
tokens = TokenManager(
    settings.jwt_secret.get_secret_value(),
    settings.access_token_minutes,
    settings.refresh_token_days,
)
login_limiter = LoginRateLimiter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]


async def current_user(session: SessionDep, credentials: CredentialsDep) -> AsyncIterator[User]:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        claims = tokens.decode(credentials.credentials, "access")
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    context_token = set_user_id(str(user.id))
    try:
        yield user
    finally:
        reset_user_id(context_token)


CurrentUserDep = Annotated[User, Depends(current_user)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    request: Request,
    session: SessionDep,
    publisher: PublisherDep,
) -> TokenResponse:
    existing = await session.scalar(select(User.id).where(User.username == payload.username))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already registered")

    user = User(
        username=payload.username,
        password_hash=await asyncio.to_thread(hash_password, payload.password),
        name=payload.name,
        date_of_birth=payload.date_of_birth,
        city=payload.city,
        state=payload.state,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already registered") from exc

    access, refresh, expires_at = tokens.issue_pair(user.id, user.username)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh),
            expires_at=expires_at,
            device_info=_device_info(request),
        )
    )
    await publisher.publish(
        _event(
            "user.registered",
            user,
            username=user.username,
            name=user.name,
            city=user.city,
        )
    )
    await session.commit()
    return TokenResponse(user_id=user.id, access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
    publisher: PublisherDep,
) -> TokenResponse:
    key = payload.username.casefold()
    if await login_limiter.is_limited(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")

    user = await session.scalar(select(User).where(User.username == payload.username))
    valid = (
        user is not None
        and user.is_active
        and await asyncio.to_thread(verify_password, payload.password, user.password_hash)
    )
    if not valid:
        await login_limiter.record_failure(key)
        raise _unauthorized("Invalid credentials")
    await login_limiter.clear(key)

    access, refresh, expires_at = tokens.issue_pair(user.id, user.username)
    device_info = _device_info(request)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh),
            expires_at=expires_at,
            device_info=device_info,
        )
    )
    await publisher.publish(_event("user.logged_in", user, device_info=device_info))
    await session.commit()
    return TokenResponse(user_id=user.id, access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, session: SessionDep) -> AccessTokenResponse:
    try:
        claims = tokens.decode(payload.refresh_token, "refresh")
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Token expired or revoked") from exc

    stored = await session.scalar(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_digest(payload.refresh_token),
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    user = await session.get(User, user_id)
    if stored is None or user is None or not user.is_active:
        raise _unauthorized("Token expired or revoked")

    stored.revoked_at = datetime.now(UTC)
    access, rotated, expires_at = tokens.issue_pair(user.id, user.username)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(rotated),
            expires_at=expires_at,
            device_info=stored.device_info,
        )
    )
    await session.commit()
    return AccessTokenResponse(access_token=access, refresh_token=rotated)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUserDep, session: SessionDep) -> Response:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUserDep) -> User:
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(user, field, value)
    if changes:
        await publisher.publish(
            _event("user.profile_updated", user, changed_fields=sorted(changes))
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Phone already registered") from exc
        await session.refresh(user)
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _device_info(request: Request) -> str | None:
    value = request.headers.get("User-Agent")
    return value[:512] if value else None


def _event(event_type: str, user: User, **fields: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "user_id": str(user.id),
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }
