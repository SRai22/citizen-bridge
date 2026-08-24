import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from contracts.lib.observability import (
    build_health,
    configure_logging,
    correlation_middleware,
    http_metrics_middleware,
    metrics_response,
    run_checks,
    setup_tracing,
)
from fastapi import FastAPI
from sqlalchemy import text
from starlette.responses import JSONResponse, Response

from app.api import router
from app.auth_client import AuthClient
from app.config import settings
from app.db.session import engine, session_factory
from app.grpc import create_server
from app.kafka import EventPublisher, UserEventConsumer
from app.service import create_grant, expire_authority

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)


async def check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def expiration_loop(publisher: EventPublisher) -> None:
    while True:
        await asyncio.sleep(settings.expiration_check_seconds)
        await expire_authority(session_factory, publisher)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    publisher = EventPublisher(settings.kafka_bootstrap_servers)
    auth_client = AuthClient(settings.auth_grpc_host)

    async def register_user(event: dict[str, object]) -> None:
        from uuid import UUID

        user_id = UUID(str(event["user_id"]))
        async with session_factory() as session:
            await create_grant(session, publisher, None, user_id, "person", user_id, "owner")

    consumer = UserEventConsumer(settings.kafka_bootstrap_servers, register_user)
    await publisher.start()
    grpc_server = create_server(settings.grpc_port, session_factory, publisher)
    await grpc_server.start()
    await consumer.start()
    expiration_task = asyncio.create_task(expiration_loop(publisher), name="authority-expiration")
    app.state.publisher = publisher
    app.state.auth_client = auth_client
    app.state.health_checks = {
        "database": check_database,
        "kafka": publisher.check,
        "auth": auth_client.check,
    }
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    try:
        yield
    finally:
        expiration_task.cancel()
        try:
            await expiration_task
        except asyncio.CancelledError:
            pass
        await consumer.stop()
        await grpc_server.stop(grace=5)
        await publisher.stop()
        await auth_client.close()
        await engine.dispose()


app = FastAPI(
    title="Citizen Bridge Authority Service",
    version=settings.service_version,
    lifespan=lifespan,
)
app.state.health_checks = {"database": check_database}
app.include_router(router)
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
    report = build_health(settings.service_name, settings.service_version, started_at, checks)
    return JSONResponse(report, status_code=200 if report["status"] == "healthy" else 503)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()
