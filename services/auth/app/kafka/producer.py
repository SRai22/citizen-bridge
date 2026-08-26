from collections.abc import Awaitable, Callable
from typing import Any

from contracts.lib.events import EventConsumer, EventProducer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedEvent


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "auth")

    async def publish(self, event: dict[str, Any]) -> None:
        await super().publish("users", event)


class DomainEventConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "auth-profile-enrichment-v1",
            ("documents", "ai"),
            sessions,
            ProcessedEvent,
        )
        self.on("document.verified", handler)
        self.on("ai.profile_extracted", handler)
