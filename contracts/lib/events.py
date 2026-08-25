import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contracts.lib.observability import kafka_headers
from contracts.lib.observability.metrics import (
    KAFKA_CONSUMED,
    KAFKA_CONSUMER_LAG,
    KAFKA_PUBLISHED,
)

Handler = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class DomainEvent:
    schema_version: str
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    occurred_at: str
    producer_service: str
    correlation_id: str
    causation_id: str | None
    payload: dict[str, Any]

    @classmethod
    def create(cls, service: str, event: dict[str, Any]) -> "DomainEvent":
        event_type = str(event["event_type"])
        aggregate_type = event_type.split(".", 1)[0]
        aggregate_id = _aggregate_id(event, aggregate_type)
        payload = {
            key: value
            for key, value in event.items()
            if key not in {"event_type", "timestamp", "event_id", "correlation_id"}
        }
        return cls(
            schema_version="1.0",
            event_id=str(event.get("event_id") or uuid4()),
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            occurred_at=str(event.get("timestamp") or datetime.now(UTC).isoformat()),
            producer_service=service,
            correlation_id=str(event.get("correlation_id") or uuid4()),
            causation_id=event.get("causation_id"),
            payload=payload,
        )

    @classmethod
    def parse(cls, value: dict[str, Any]) -> "DomainEvent":
        if value.get("schema_version"):
            return cls(**value)
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        event_type = str(value["event_type"])
        aggregate_type = event_type.split(".", 1)[0]
        return cls(
            schema_version="1.0",
            event_id=str(uuid5(NAMESPACE_URL, canonical)),
            event_type=event_type,
            aggregate_id=_aggregate_id(value, aggregate_type),
            aggregate_type=aggregate_type,
            occurred_at=str(value.get("timestamp") or datetime.now(UTC).isoformat()),
            producer_service="legacy",
            correlation_id=str(uuid5(NAMESPACE_URL, f"correlation:{canonical}")),
            causation_id=None,
            payload={
                key: item
                for key, item in value.items()
                if key not in {"event_type", "timestamp"}
            },
        )

    def handler_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.occurred_at,
            "correlation_id": self.correlation_id,
            **self.payload,
        }


class EventProducer:
    def __init__(self, bootstrap_servers: str, service_name: str) -> None:
        self.producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode(),
        )
        self.service_name = service_name

    async def start(self) -> None:
        await self.producer.start()

    async def stop(self) -> None:
        await self.producer.stop()

    async def check(self) -> None:
        await self.producer.client.fetch_all_metadata()

    async def publish(self, topic: str, value: dict[str, Any]) -> DomainEvent:
        event = DomainEvent.create(self.service_name, value)
        await self.producer.send_and_wait(
            topic,
            asdict(event),
            key=event.aggregate_id.encode(),
            headers=kafka_headers(),
        )
        KAFKA_PUBLISHED.labels(topic, event.event_type).inc()
        return event


class EventConsumer:
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: tuple[str, ...],
        sessions: async_sessionmaker[AsyncSession],
        processed_model: type,
    ) -> None:
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self.dlq = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode(),
        )
        self.group_id = group_id
        self.sessions = sessions
        self.processed_model = processed_model
        self.handlers: dict[str, Handler] = {}
        self.task: asyncio.Task[None] | None = None

    def on(self, event_type: str, handler: Handler) -> None:
        self.handlers[event_type] = handler

    async def start(self) -> None:
        await self.consumer.start()
        await self.dlq.start()
        self.task = asyncio.create_task(self._run(), name=f"{self.group_id}-consumer")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.consumer.stop()
        await self.dlq.stop()

    async def check(self) -> None:
        await self.consumer._client.fetch_all_metadata()

    async def _run(self) -> None:
        async for message in self.consumer:
            event = DomainEvent.parse(json.loads(message.value))
            if not await self._seen(event.event_id):
                handler = self.handlers.get(event.event_type)
                if handler and not await self._handle(message.topic, event, handler):
                    await self.consumer.commit()
                    continue
                await self._mark(event.event_id)
            KAFKA_CONSUMED.labels(message.topic, event.event_type).inc()
            highwater = self.consumer.highwater(TopicPartition(message.topic, message.partition))
            if highwater is not None:
                KAFKA_CONSUMER_LAG.labels(message.topic, message.partition).set(
                    max(0, highwater - message.offset - 1)
                )
            await self.consumer.commit()

    async def _handle(self, topic: str, event: DomainEvent, handler: Handler) -> bool:
        for attempt in range(1, 4):
            try:
                await handler(event.handler_payload())
                return True
            except Exception as exc:
                if attempt == 3:
                    await self.dlq.send_and_wait(
                        f"{topic}.dlq",
                        {
                            "original_event": asdict(event),
                            "error": str(exc),
                            "retry_count": attempt,
                            "failed_at": datetime.now(UTC).isoformat(),
                        },
                        key=event.aggregate_id.encode(),
                    )
                else:
                    await asyncio.sleep(0)
        return False

    async def _seen(self, event_id: str) -> bool:
        async with self.sessions() as session:
            return await session.get(self.processed_model, event_id) is not None

    async def _mark(self, event_id: str) -> None:
        async with self.sessions() as session:
            session.add(self.processed_model(event_id=event_id, consumer_group=self.group_id))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()


def _aggregate_id(event: dict[str, Any], aggregate_type: str) -> str:
    for key in (
        f"{aggregate_type}_id",
        "conversation_id",
        "task_id",
        "case_id",
        "document_id",
        "user_id",
        "grant_id",
        "delegation_id",
        "delegation_request_id",
        "notification_id",
    ):
        if event.get(key):
            return str(event[key])
    raise ValueError(f"{event['event_type']} requires an aggregate ID")
