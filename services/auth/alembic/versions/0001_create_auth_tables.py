"""Create auth users and refresh tokens."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_auth"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("aadhaar_linked", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index("ix_auth_users_username", "users", ["username"], unique=True, schema="auth")
    op.create_index("ix_auth_users_phone", "users", ["phone"], unique=True, schema="auth")

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_info", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        "ix_auth_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("refresh_tokens", schema="auth")
    op.drop_table("users", schema="auth")
