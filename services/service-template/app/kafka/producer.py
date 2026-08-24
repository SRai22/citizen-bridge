from aiokafka import AIOKafkaProducer

from app.config import settings


def create_producer() -> AIOKafkaProducer:
    return AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
