import json
from typing import Any

from aiokafka import AIOKafkaProducer
from contracts.lib.observability import kafka_headers
from contracts.lib.observability.metrics import KAFKA_PUBLISHED


class EventPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda value: json.dumps(value).encode(),
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def check(self) -> None:
        await self._producer.client.fetch_all_metadata()

    async def publish(self, event: dict[str, Any]) -> None:
        event_type = str(event["event_type"])
        await self._producer.send_and_wait("users", event, headers=kafka_headers())
        KAFKA_PUBLISHED.labels("users", event_type).inc()
