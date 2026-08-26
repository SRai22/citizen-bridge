from collections.abc import Awaitable, Callable

from contracts.lib.events import EventConsumer, EventProducer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ProcessedEvent

TOPICS = ("cases", "tasks", "documents", "users", "authority", "benefits")
EVENT_TYPES = (
    "case.created",
    "case.completed",
    "task.status_changed",
    "task.completed",
    "task.failed",
    "document.created",
    "document.accessed",
    "document.expired",
    "authority.granted",
    "authority.revoked",
    "user.profile_updated",
    "user.logged_in",
    "benefit.discovered",
)


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "notifications")

    async def publish(self, event: dict) -> None:
        await super().publish("notifications", event)


class DomainEventConsumer(EventConsumer):
    def __init__(
        self,
        bootstrap_servers: str,
        sessions: async_sessionmaker[AsyncSession],
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        super().__init__(
            bootstrap_servers,
            "notifications-domain-events-v1",
            TOPICS,
            sessions,
            ProcessedEvent,
        )
        for event_type in EVENT_TYPES:
            self.on(event_type, handler)
