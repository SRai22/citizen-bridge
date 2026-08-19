"""FastAPI application entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response returned by the service health endpoint."""

    status: str


def create_app() -> FastAPI:
    """Create and configure the Citizen Bridge API."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    application = FastAPI(title="Citizen Bridge API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return application


app = create_app()
