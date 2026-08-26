from collections.abc import Awaitable, Callable
from typing import Any

from contracts.lib.events import EventConsumer, EventProducer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedEvent


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "documents")

    async def publish(self, event: dict[str, Any]) -> None:
        await super().publish("documents", event)


class TaskConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "documents-task-events-v1",
            ("tasks",),
            sessions,
            ProcessedEvent,
        )
        self.on("task.completed", handler)


class UserDeletionConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "documents-user-deletion-v1",
            ("users",),
            sessions,
            ProcessedEvent,
        )
        self.on("user.deleted", handler)
