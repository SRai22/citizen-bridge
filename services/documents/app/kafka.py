import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from contracts.lib.observability import kafka_headers
from contracts.lib.observability.metrics import KAFKA_CONSUMED, KAFKA_PUBLISHED


class EventPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode(),
        )

    async def start(self) -> None:
        await self.producer.start()

    async def stop(self) -> None:
        await self.producer.stop()

    async def check(self) -> None:
        await self.producer.client.fetch_all_metadata()

    async def publish(self, event: dict[str, Any]) -> None:
        await self.producer.send_and_wait("documents", event, headers=kafka_headers())
        KAFKA_PUBLISHED.labels("documents", str(event["event_type"])).inc()


class TaskConsumer:
    def __init__(
        self, bootstrap_servers: str, handler: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        self.consumer = AIOKafkaConsumer(
            "tasks",
            bootstrap_servers=bootstrap_servers,
            group_id="documents-task-events-v1",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self.handler = handler
        self.task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.consumer.start()
        self.task = asyncio.create_task(self._run(), name="documents-task-consumer")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.consumer.stop()

    async def _run(self) -> None:
        async for message in self.consumer:
            event = json.loads(message.value)
            if event.get("event_type") == "task.completed":
                await self.handler(event)
            KAFKA_CONSUMED.labels("tasks", str(event.get("event_type", "unknown"))).inc()
            await self.consumer.commit()
