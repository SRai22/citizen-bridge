from collections.abc import Awaitable, Callable
from typing import Any

from contracts.lib.events import EventConsumer, EventProducer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedEvent


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "ai")

    async def publish(self, event: dict[str, Any]) -> None:
        await super().publish("ai", event)


class UserDeletionConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "ai-user-deletion-v1",
            ("users",),
            sessions,
            ProcessedEvent,
        )
        self.on("user.deleted", handler)
