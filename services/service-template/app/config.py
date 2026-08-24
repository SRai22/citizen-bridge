from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str
    database_url: str
    jwt_secret: SecretStr
    kafka_bootstrap_servers: str = "kafka:9092"
    http_port: int = 8000
    grpc_port: int = 50051
    service_version: str = "0.1.0"
    auth_grpc_host: str = "auth:50051"
    authority_grpc_host: str = "authority:50052"
    ai_mock_mode: bool = False
    enable_websocket: bool = False
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or secret == "change-me-in-production":
            raise ValueError(
                "JWT_SECRET must be at least 32 characters and not a placeholder"
            )
        return value


settings = Settings()
