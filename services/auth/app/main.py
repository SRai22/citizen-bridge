from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

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

from app.api import router, tokens
from app.clients import CatalogClient
from app.config import settings
from app.db.session import engine, session_factory
from app.grpc import create_server
from app.kafka import DomainEventConsumer, EventPublisher
from app.models import User
from app.profile import enrich_profile, fields_from_event

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)


async def check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    publisher = EventPublisher(settings.kafka_bootstrap_servers)
    catalog = CatalogClient(settings.catalog_http_url)

    async def consume(event: dict) -> None:
        parsed = fields_from_event(event)
        if parsed is None:
            return
        user_id, fields = parsed
        async with session_factory() as session:
            user = await session.get(User, UUID(user_id))
            if user is None:
                return
            changed = await enrich_profile(session, user, fields)
            await publisher.publish(
                {
                    "event_type": "user.profile_updated",
                    "user_id": str(user.id),
                    "changed_fields": changed,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await session.commit()

    consumer = DomainEventConsumer(
        settings.kafka_bootstrap_servers, session_factory, consume
    )
    grpc_server = create_server(settings.grpc_port, session_factory, tokens)
    await publisher.start()
    await grpc_server.start()
    await consumer.start()
    app.state.publisher = publisher
    app.state.catalog_client = catalog
    app.state.health_checks = {"database": check_database, "kafka": consumer.check}
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    try:
        yield
    finally:
        await consumer.stop()
        await grpc_server.stop(grace=5)
        await publisher.stop()
        await catalog.close()
        await engine.dispose()


app = FastAPI(
    title="Citizen Bridge Auth Service",
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
