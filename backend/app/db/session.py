"""Async database engine and session lifecycle."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base


def to_async_url(database_url: str) -> str:
    """Convert a conventional SQLite URL to SQLAlchemy's async driver URL."""
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return database_url


def ensure_sqlite_directory(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite database."""
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Build an async engine with SQLite foreign-key enforcement enabled."""
    async_url = to_async_url(database_url)
    ensure_sqlite_directory(async_url)
    database_engine = create_async_engine(async_url, echo=echo)

    if make_url(async_url).drivername.startswith("sqlite"):

        @event.listens_for(database_engine.sync_engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


database_url = os.getenv("DATABASE_URL", "sqlite:///./data/citizen_bridge.db")
engine = create_database_engine(database_url)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db(database_engine: AsyncEngine = engine) -> None:
    """Create all known tables when the configured database is first used."""
    # Import model modules so their tables are registered on Base.metadata.
    import app.models  # noqa: F401

    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a transaction-capable session for FastAPI dependencies."""
    async with AsyncSessionFactory() as session:
        yield session
