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
from starlette.responses import JSONResponse, Response

from app.api import router
from app.catalog import Catalog
from app.config import settings
from app.grpc import create_server

started_at = datetime.now(UTC)
logger = configure_logging(settings.service_name)
catalog = Catalog(settings.catalog_data_dir)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    catalog.reload()
    grpc_server = create_server(settings.grpc_port, catalog)
    await grpc_server.start()
    logger.info(
        "service.started",
        extra={"http_port": settings.http_port, "grpc_port": settings.grpc_port},
    )
    try:
        yield
    finally:
        await grpc_server.stop(grace=5)


app = FastAPI(title="Citizen Bridge Catalog", version=settings.service_version, lifespan=lifespan)
app.state.catalog = catalog
app.state.health_checks = {"catalog": catalog.check}
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
