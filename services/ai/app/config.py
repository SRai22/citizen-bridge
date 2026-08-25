from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "ai"
    service_version: str = "0.1.0"
    database_url: str
    kafka_bootstrap_servers: str = "kafka:9092"
    auth_grpc_host: str = "auth:50051"
    http_port: int = 8007
    grpc_port: int = 50057
    ai_mock_mode: bool = True
    openai_api_key: str = ""
    intake_model: str = "gpt-4o-mini"
    rejection_model: str = "gpt-4o"
    intake_input_cost_per_million: float = 0.15
    intake_output_cost_per_million: float = 0.60
    rejection_input_cost_per_million: float = 2.50
    rejection_output_cost_per_million: float = 10.00
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"


settings = Settings()
