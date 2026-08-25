from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "catalog"
    service_version: str = "0.1.0"
    http_port: int = 8006
    grpc_port: int = 50056
    catalog_data_dir: Path = Path(__file__).parent / "data"
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"


settings = Settings()
