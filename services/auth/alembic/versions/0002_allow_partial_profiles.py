"""Allow accounts created after phone verification to have partial profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_partial_profiles"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("name", "date_of_birth", "city"):
        op.alter_column("users", column, nullable=True, schema="auth")


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE auth.users SET name = COALESCE(name, ''), "
            "date_of_birth = COALESCE(date_of_birth, DATE '1900-01-01'), "
            "city = COALESCE(city, '')"
        )
    )
    for column in ("name", "date_of_birth", "city"):
        op.alter_column("users", column, nullable=False, schema="auth")
