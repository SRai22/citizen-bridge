import asyncio
import json
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from contracts.lib.observability.metrics import KAFKA_CONSUMED

TOPICS = ("cases", "tasks", "documents", "users", "authority")


class DomainEventConsumer:
    def __init__(self, bootstrap_servers: str, handler: Callable[[dict], Awaitable[None]]) -> None:
        self.consumer = AIOKafkaConsumer(
            *TOPICS,
            bootstrap_servers=bootstrap_servers,
            group_id="notifications-domain-events-v1",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self.handler = handler
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.consumer.start()
        self.task = asyncio.create_task(self._run(), name="notifications-domain-consumer")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.consumer.stop()

    async def check(self) -> None:
        await self.consumer._client.fetch_all_metadata()

    async def _run(self) -> None:
        async for message in self.consumer:
            event = json.loads(message.value)
            await self.handler(event)
            KAFKA_CONSUMED.labels(message.topic, str(event.get("event_type", "unknown"))).inc()
            await self.consumer.commit()
