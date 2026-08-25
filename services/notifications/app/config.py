from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    service_name: str = "notifications"
    service_version: str = "0.1.0"
    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    auth_grpc_host: str = "auth:50051"
    authority_grpc_host: str = "authority:50052"
    http_port: int = 8005
    grpc_port: int = 50055
    digest_check_seconds: int = 3600
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"


settings = Settings()
