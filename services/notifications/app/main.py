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
from app.clients import AuthClient, AuthorityClient
from app.config import settings
from app.db.session import engine, session_factory
from app.grpc import create_server
from app.kafka import DomainEventConsumer
from app.service import generate_weekly_digests, handle_event
from app.websocket import ConnectionManager

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)
connections = ConnectionManager()


async def check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def digest_loop() -> None:
    while True:
        now = datetime.now(UTC)
        if now.hour >= 9:
            await generate_weekly_digests(
                session_factory, connections, now.strftime("%A").casefold()
            )
        await asyncio.sleep(settings.digest_check_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    auth = AuthClient(settings.auth_grpc_host)
    authority = AuthorityClient(settings.authority_grpc_host)

    async def consume(event: dict) -> None:
        async with session_factory() as session:
            await handle_event(session, connections, authority, event)

    consumer = DomainEventConsumer(settings.kafka_bootstrap_servers, consume)
    grpc_server = create_server(settings.grpc_port, session_factory, connections)
    await grpc_server.start()
    await consumer.start()
    digests = asyncio.create_task(digest_loop(), name="notification-digests")
    app.state.auth_client = auth
    app.state.authority_client = authority
    app.state.connections = connections
    app.state.health_checks = {
        "database": check_database,
        "kafka": consumer.check,
        "auth": auth.check,
        "authority": authority.check,
    }
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    try:
        yield
    finally:
        digests.cancel()
        try:
            await digests
        except asyncio.CancelledError:
            pass
        await consumer.stop()
        await grpc_server.stop(grace=5)
        await authority.close()
        await auth.close()
        await engine.dispose()


app = FastAPI(
    title="Citizen Bridge Notifications", version=settings.service_version, lifespan=lifespan
)
app.state.health_checks = {"database": check_database}
app.state.connections = connections
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
