from typing import Any

from contracts.lib.events import EventProducer


class EventPublisher(EventProducer):
    def __init__(self, bootstrap_servers: str) -> None:
        super().__init__(bootstrap_servers, "auth")

    async def publish(self, event: dict[str, Any]) -> None:
        await super().publish("users", event)
