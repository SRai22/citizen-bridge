from collections.abc import Awaitable, Callable
from typing import Any

from contracts.lib.events import EventConsumer, EventProducer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedEvent


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "case-engine")

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        await super().publish(topic, event)


class ProfileEventConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict], Awaitable[None]],
        deletion_handler: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "case-benefit-discovery-v1",
            ("users",),
            sessions,
            ProcessedEvent,
        )
        self.on("user.profile_updated", handler)
        if deletion_handler:
            self.on("user.deleted", deletion_handler)
