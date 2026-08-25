from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401
from app.config import settings
from app.db.base import Base
from sqlalchemy import engine_from_config, pool

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "+psycopg"))
if config.config_file_name:
    fileConfig(config.config_file_name)


def options() -> dict[str, object]:
    return {"target_metadata": Base.metadata, "version_table_schema": "ai"}


if context.is_offline_mode():
    context.configure(url=config.get_main_option("sqlalchemy.url"), **options())
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        context.configure(connection=connection, **options())
        with context.begin_transaction():
            context.run_migrations()
