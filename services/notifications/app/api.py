import hmac
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import AuthClient
from app.config import settings
from app.db import get_session
from app.db.session import session_factory
from app.models import ActivityEntry, Notification
from app.schemas import ActivityResponse, NotificationResponse, PreferencePatch, PreferenceResponse
from app.service import digest, mark_read, preference, update_preference, websocket_message
from app.websocket import ConnectionManager

router = APIRouter(tags=["notifications"])
internal_router = APIRouter(prefix="/internal", include_in_schema=False)
bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def auth_client(request: Request) -> AuthClient:
    return request.app.state.auth_client


AuthDep = Annotated[AuthClient, Depends(auth_client)]


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


@router.get("/api/notifications")
async def notifications(
    user_id: UserDep,
    session: SessionDep,
    unread_only: bool = False,
    type_filter: Annotated[str | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = [Notification.user_id == user_id]
    if unread_only:
        filters.append(Notification.read.is_(False))
    if type_filter:
        filters.append(
            or_(
                Notification.notification_type == type_filter,
                Notification.priority == type_filter,
            )
        )
    rows = (
        await session.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    return {
        "notifications": [NotificationResponse.model_validate(item).model_dump() for item in rows],
        "unread_count": unread or 0,
    }


@router.post("/api/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(user_id: UserDep, session: SessionDep) -> Response:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
        .values(read=True, read_at=func.now())
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/notifications/digest")
async def weekly_digest(user_id: UserDep, session: SessionDep, week: str | None = None) -> dict:
    try:
        return await digest(session, user_id, week)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/api/notifications/preferences", response_model=PreferenceResponse)
async def get_preferences(user_id: UserDep, session: SessionDep):
    return await preference(session, user_id)


@router.patch("/api/notifications/preferences", response_model=PreferenceResponse)
async def patch_preferences(payload: PreferencePatch, user_id: UserDep, session: SessionDep):
    return await update_preference(session, user_id, payload)


@router.patch("/api/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_notification(
    notification_id: UUID, user_id: UserDep, session: SessionDep
) -> Response:
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    await mark_read(session, notification)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/notifications/activity")
async def activity_feed(
    user_id: UserDep,
    session: SessionDep,
    category: str | None = None,
    days: Annotated[int, Query(ge=1, le=90)] = 90,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = [
        ActivityEntry.user_id == user_id,
        ActivityEntry.occurred_at >= datetime.now(UTC) - timedelta(days=days),
    ]
    if category:
        categories = {
            "cases": ("cases", "submissions"),
            "documents": ("documents", "sharing"),
        }.get(category, (category,))
        filters.append(ActivityEntry.category.in_(categories))
    total_filters = [ActivityEntry.user_id == user_id]
    if category:
        total_filters.append(ActivityEntry.category.in_(categories))
    total = await session.scalar(
        select(func.count()).select_from(ActivityEntry).where(*total_filters)
    )
    rows = (
        await session.scalars(
            select(ActivityEntry)
            .where(*filters)
            .order_by(ActivityEntry.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    activities = [ActivityResponse.model_validate(row).model_dump() for row in rows]
    groups: dict[str, list[dict]] = {}
    for item in activities:
        groups.setdefault(item["occurred_at"].date().isoformat(), []).append(item)
    return {
        "activities": activities,
        "groups": [{"date": day, "activities": items} for day, items in groups.items()],
        "has_more": offset + len(rows) < (total or 0),
    }


@router.get("/api/notifications/audit-log")
async def audit_log(
    user_id: UserDep,
    session: SessionDep,
    category: str | None = None,
    document_id: UUID | None = None,
    case_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    filters = [ActivityEntry.user_id == user_id]
    if category:
        filters.append(ActivityEntry.category == category)
    if document_id:
        filters.append(ActivityEntry.document_id == document_id)
    if case_id:
        filters.append(ActivityEntry.case_id == case_id)
    rows = (
        await session.scalars(
            select(ActivityEntry)
            .where(*filters)
            .order_by(ActivityEntry.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "entries": [
            {
                **ActivityResponse.model_validate(row).model_dump(exclude={"data"}),
                "details": row.data,
            }
            for row in rows
        ]
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
    notifications = (
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at)
        )
    ).all()
    activities = (
        await session.scalars(
            select(ActivityEntry)
            .where(ActivityEntry.user_id == user_id)
            .order_by(ActivityEntry.occurred_at)
        )
    ).all()
    return {
        "notification_history": [
            NotificationResponse.model_validate(row).model_dump() for row in notifications
        ],
        "activity_log": [ActivityResponse.model_validate(row).model_dump() for row in activities],
    }


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    last_event_id: UUID | None = None,
) -> None:
    auth: AuthClient = websocket.app.state.auth_client
    manager: ConnectionManager = websocket.app.state.connections
    try:
        validation = await auth.validate(token)
    except ConnectionError:
        await websocket.close(code=1013)
        return
    if not validation.valid:
        await websocket.close(code=1008)
        return
    user_id = validation.user_id
    await manager.connect(websocket, user_id)
    try:
        async with session_factory() as session:
            query = select(Notification).where(Notification.user_id == UUID(user_id))
            if last_event_id:
                last = await session.scalar(
                    select(Notification).where(
                        Notification.id == last_event_id,
                        Notification.user_id == UUID(user_id),
                    )
                )
                if last:
                    query = query.where(Notification.created_at > last.created_at)
            missed = (await session.scalars(query.order_by(Notification.created_at))).all()
            for notification in missed:
                await websocket.send_json(websocket_message(notification))
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "ack" or not message.get("notification_id"):
                continue
            async with session_factory() as session:
                notification = await session.scalar(
                    select(Notification).where(
                        Notification.id == UUID(message["notification_id"]),
                        Notification.user_id == UUID(user_id),
                    )
                )
                if notification:
                    await mark_read(session, notification)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        manager.disconnect(websocket, user_id)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )
