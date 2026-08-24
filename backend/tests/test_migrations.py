import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_sqlite_migration_commits_revision(tmp_path: Path) -> None:
    database = tmp_path / "migration.db"
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database}",
        "ALEMBIC_CONFIG": str(Path(__file__).parents[1] / "alembic.ini"),
    }

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.db.migrations import upgrade_database; upgrade_database()",
        ],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=True,
    )

    with sqlite3.connect(database) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()

    assert revision == ("2f9fa12c5504",)
