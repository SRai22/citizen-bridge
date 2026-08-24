import json
from typing import Any

from aiokafka import AIOKafkaProducer
from contracts.lib.observability import kafka_headers
from contracts.lib.observability.metrics import KAFKA_PUBLISHED


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

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        event_type = str(event["event_type"])
        await self.producer.send_and_wait(topic, event, headers=kafka_headers())
        KAFKA_PUBLISHED.labels(topic, event_type).inc()
