"""Programmatic Alembic migration entry point for application startup."""

import asyncio
import os
from pathlib import Path

from alembic.config import Config

from alembic import command


def upgrade_database() -> None:
    """Synchronously upgrade the configured database to the latest revision."""
    config_path = Path(os.getenv("ALEMBIC_CONFIG", "alembic.ini")).resolve()
    alembic_config = Config(config_path)
    command.upgrade(alembic_config, "head")


async def migrate_database() -> None:
    """Run blocking migration work away from FastAPI's event loop."""
    await asyncio.to_thread(upgrade_database)
