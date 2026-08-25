from uuid import UUID

import grpc
from contracts.generated import notifications_pb2, notifications_pb2_grpc
from grpc import aio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Notification
from app.schemas import NotificationCreate
from app.service import create_notification, mark_read
from app.websocket import ConnectionManager


class NotificationServicer(notifications_pb2_grpc.NotificationServiceServicer):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        manager: ConnectionManager,
    ) -> None:
        self.sessions = sessions
        self.manager = manager

    async def CreateNotification(self, request, context):  # noqa: N802
        try:
            payload = NotificationCreate(
                user_id=UUID(request.user_id),
                notification_type=request.type,
                title=request.title,
                body=request.body,
            )
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        async with self.sessions() as session:
            notification = await create_notification(session, self.manager, payload)
        return _response(notification)

    async def MarkRead(self, request, context):  # noqa: N802
        try:
            user_id = UUID(request.user_id)
            notification_id = UUID(request.notification_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid UUID")
        async with self.sessions() as session:
            notification = await session.get(Notification, notification_id)
            if notification is None or notification.user_id != user_id:
                await context.abort(grpc.StatusCode.NOT_FOUND, "Notification not found")
            await mark_read(session, notification)
        return _response(notification)


def _response(notification: Notification):
    return notifications_pb2.NotificationResponse(
        notification_id=str(notification.id), read=notification.read
    )


def create_server(
    port: int,
    sessions: async_sessionmaker[AsyncSession],
    manager: ConnectionManager,
) -> aio.Server:
    server = aio.server()
    notifications_pb2_grpc.add_NotificationServiceServicer_to_server(
        NotificationServicer(sessions, manager), server
    )
    server.add_insecure_port(f"[::]:{port}")
    return server
