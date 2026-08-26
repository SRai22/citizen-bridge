from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    service_name: str = "documents"
    service_version: str = "0.1.0"
    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    auth_grpc_host: str = "auth:50051"
    internal_service_token: SecretStr = SecretStr("")
    http_port: int = 8004
    grpc_port: int = 50054
    expiration_check_seconds: int = 3600
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"

    @field_validator("expiration_check_seconds")
    @classmethod
    def positive_interval(cls, value: int) -> int:
        if value < 1:
            raise ValueError("EXPIRATION_CHECK_SECONDS must be positive")
        return value


settings = Settings()
