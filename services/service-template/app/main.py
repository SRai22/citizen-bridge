from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, WebSocket
from sqlalchemy import text
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.db.session import engine
from app.grpc.server import create_server
from contracts.lib.observability import (
    build_health,
    configure_logging,
    correlation_middleware,
    http_metrics_middleware,
    metrics_response,
    run_checks,
    setup_tracing,
)

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)


async def check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_kafka() -> None:
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await producer.start()
    finally:
        await producer.stop()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    grpc_server = create_server(settings.grpc_port)
    await grpc_server.start()
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    yield
    await grpc_server.stop(grace=5)
    await engine.dispose()


app = FastAPI(
    title=settings.service_name, version=settings.service_version, lifespan=lifespan
)
app.state.health_checks = {"database": check_database, "kafka": check_kafka}
app.middleware("http")(http_metrics_middleware)
app.middleware("http")(correlation_middleware)
setup_tracing(
    settings.service_name,
    app,
    settings.otel_exporter_otlp_endpoint,
    enabled=settings.otel_enabled,
)


@app.get("/health")
async def health() -> JSONResponse:
    checks = await run_checks(app.state.health_checks)
    report = build_health(
        settings.service_name, settings.service_version, started_at, checks
    )
    return JSONResponse(
        report, status_code=200 if report["status"] == "healthy" else 503
    )


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()


if settings.enable_websocket:

    @app.websocket("/ws/health")
    async def websocket_health(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json(
            {"service": settings.service_name, "status": "healthy"}
        )
        await websocket.close()
