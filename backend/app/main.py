"""FastAPI application entry point."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api import cases_router, tasks_router
from app.db.migrations import migrate_database
from app.db.session import engine


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    status: str


def create_app() -> FastAPI:
    """Create and configure the Citizen Bridge API."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await migrate_database()
        yield
        await engine.dispose()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    application = FastAPI(
        title="Citizen Bridge API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(cases_router)
    application.include_router(tasks_router)

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return application


app = create_app()
