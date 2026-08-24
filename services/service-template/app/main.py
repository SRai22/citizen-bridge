from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db.session import engine
from app.grpc.server import create_server


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    grpc_server = create_server(settings.grpc_port)
    await grpc_server.start()
    yield
    await grpc_server.stop(grace=5)
    await engine.dispose()


app = FastAPI(title=settings.service_name, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}
