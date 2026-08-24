import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "service-template")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://service:service@postgres:5432/citizen_bridge",
    )
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    grpc_port: int = int(os.getenv("GRPC_PORT", "50051"))


settings = Settings()
