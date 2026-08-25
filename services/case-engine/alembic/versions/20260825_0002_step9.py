"""Add case subject context and task waiting state."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260825_0002"
down_revision = "20260824_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("cases", schema="cases")}
    if "subject_person_id" not in columns:
        op.add_column(
            "cases", sa.Column("subject_person_id", postgresql.UUID()), schema="cases"
        )
        op.create_index(
            "ix_cases_cases_subject_person_id",
            "cases",
            ["subject_person_id"],
            schema="cases",
        )
    if "coordinator_user_id" not in columns:
        op.add_column(
            "cases", sa.Column("coordinator_user_id", postgresql.UUID()), schema="cases"
        )
        op.create_index(
            "ix_cases_cases_coordinator_user_id",
            "cases",
            ["coordinator_user_id"],
            schema="cases",
        )
    if "subject_relationship" not in columns:
        op.add_column(
            "cases", sa.Column("subject_relationship", sa.String(100)), schema="cases"
        )
    if "task_wait_states" not in inspector.get_table_names(schema="cases"):
        _create_wait_states()


def _create_wait_states() -> None:
    op.create_table(
        "task_wait_states",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("task_id", postgresql.UUID(), nullable=False, unique=True),
        sa.Column("stages_known", sa.Boolean(), nullable=False),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("current_stage", sa.String(100)),
        sa.Column("stage_entered_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_wait_days_min", sa.Integer()),
        sa.Column("estimated_wait_days_max", sa.Integer()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_update_at", sa.DateTime(timezone=True)),
        sa.Column("is_overdue", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["cases.tasks.id"], ondelete="CASCADE"),
        schema="cases",
    )
    op.create_index(
        "ix_cases_task_wait_states_task_id",
        "task_wait_states",
        ["task_id"],
        unique=True,
        schema="cases",
    )


def downgrade() -> None:
    op.drop_table("task_wait_states", schema="cases")
    op.drop_index("ix_cases_cases_coordinator_user_id", table_name="cases", schema="cases")
    op.drop_index("ix_cases_cases_subject_person_id", table_name="cases", schema="cases")
    op.drop_column("cases", "subject_relationship", schema="cases")
    op.drop_column("cases", "coordinator_user_id", schema="cases")
    op.drop_column("cases", "subject_person_id", schema="cases")
