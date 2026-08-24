"""Create authority grants, case access, and delegations."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_authority"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authority_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grantor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("grantee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resource_type IN ('case', 'person', 'document', 'household')",
            name="ck_authority_grants_resource_type",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'coordinator', 'viewer')",
            name="ck_authority_grants_role",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="authority",
    )
    op.create_index(
        "ix_authority_authority_grants_grantor_id",
        "authority_grants",
        ["grantor_id"],
        schema="authority",
    )
    op.create_index(
        "ix_authority_authority_grants_grantee_id",
        "authority_grants",
        ["grantee_id"],
        schema="authority",
    )
    op.create_index(
        "ix_authority_active_resource",
        "authority_grants",
        ["grantee_id", "resource_type", "resource_id", "revoked_at"],
        schema="authority",
    )

    op.create_table(
        "case_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["grant_id"], ["authority.authority_grants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grant_id"),
        sa.UniqueConstraint("user_id", "case_id", name="uq_authority_case_access_user_case"),
        schema="authority",
    )
    op.create_index(
        "ix_authority_case_access_user_id",
        "case_access",
        ["user_id"],
        schema="authority",
    )
    op.create_index(
        "ix_authority_case_access_case_id",
        "case_access",
        ["case_id"],
        schema="authority",
    )

    op.create_table(
        "delegations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('case', 'person', 'all_cases')",
            name="ck_authority_delegations_scope_type",
        ),
        sa.CheckConstraint(
            "role IN ('coordinator', 'viewer')", name="ck_authority_delegations_role"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name="ck_authority_delegations_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="authority",
    )
    op.create_index(
        "ix_authority_delegations_delegator_id",
        "delegations",
        ["delegator_id"],
        schema="authority",
    )
    op.create_index(
        "ix_authority_delegations_delegate_id",
        "delegations",
        ["delegate_id"],
        schema="authority",
    )
    op.create_index(
        "ix_authority_active_delegations",
        "delegations",
        ["delegate_id", "status"],
        schema="authority",
    )


def downgrade() -> None:
    op.drop_table("delegations", schema="authority")
    op.drop_table("case_access", schema="authority")
    op.drop_table("authority_grants", schema="authority")
