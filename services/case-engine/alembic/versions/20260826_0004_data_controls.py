"""Add case ownership and cancelled tasks."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260826_0004"
down_revision = "20260825_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("cases", schema="cases")}
    if "owner_user_id" not in columns:
        op.add_column(
            "cases",
            sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            schema="cases",
        )

    indexes = {index["name"] for index in inspector.get_indexes("cases", schema="cases")}
    if "ix_cases_cases_owner_user_id" not in indexes:
        op.create_index(
            "ix_cases_cases_owner_user_id", "cases", ["owner_user_id"], schema="cases"
        )
    op.execute(
        """
        UPDATE cases.cases AS citizen_case
        SET owner_user_id = CAST(audit.details->>'user_id' AS uuid)
        FROM cases.audit_entries AS audit
        WHERE audit.case_id = citizen_case.id
          AND audit.event_type = 'case_created'
          AND audit.details->>'user_id' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_cases_cases_owner_user_id", table_name="cases", schema="cases")
    op.drop_column("cases", "owner_user_id", schema="cases")
