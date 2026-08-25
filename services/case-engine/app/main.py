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

from app.api import approvals_router, router
from app.clients import AIClient, AuthClient, AuthorityClient, CatalogClient
from app.config import settings
from app.db.session import engine, session_factory
from app.grpc import create_server
from app.kafka import EventPublisher
from app.service import mark_overdue_tasks

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)


async def check_database() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def overdue_loop() -> None:
    while True:
        await asyncio.sleep(settings.overdue_check_seconds)
        async with session_factory() as session:
            await mark_overdue_tasks(session)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    auth = AuthClient(settings.auth_grpc_host)
    authority = AuthorityClient(settings.authority_grpc_host)
    catalog_client = CatalogClient(settings.catalog_grpc_host)
    ai_client = AIClient(settings.ai_grpc_host)
    events = EventPublisher(settings.kafka_bootstrap_servers)
    await events.start()
    grpc_server = create_server(settings.grpc_port, session_factory)
    await grpc_server.start()
    overdue_task = asyncio.create_task(overdue_loop(), name="case-overdue-tasks")
    app.state.auth_client = auth
    app.state.authority_client = authority
    app.state.catalog_client = catalog_client
    app.state.ai_client = ai_client
    app.state.publisher = events
    app.state.health_checks = {
        "database": check_database,
        "kafka": events.check,
        "auth": auth.check,
        "authority": authority.check,
        "catalog": catalog_client.check,
        "ai": ai_client.check,
    }
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    try:
        yield
    finally:
        overdue_task.cancel()
        try:
            await overdue_task
        except asyncio.CancelledError:
            pass
        await grpc_server.stop(grace=5)
        await events.stop()
        await authority.close()
        await catalog_client.close()
        await ai_client.close()
        await auth.close()
        await engine.dispose()


app = FastAPI(
    title="Citizen Bridge Case Engine",
    version=settings.service_version,
    lifespan=lifespan,
)
app.state.health_checks = {"database": check_database}
app.include_router(router)
app.include_router(approvals_router)
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
