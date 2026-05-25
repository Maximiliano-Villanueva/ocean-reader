"""Add archive / soft-delete timestamps to validation_runs (M2 run history lifecycle)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_validation_runs_lifecycle"
down_revision: Union[str, Sequence[str], None] = "009_validation_runs_m2_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "validation_runs",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_validation_runs_project_active_list",
        "validation_runs",
        ["project_id", "created_at"],
        postgresql_where=sa.text("archived_at IS NULL AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_project_active_list", table_name="validation_runs")
    op.drop_column("validation_runs", "deleted_at")
    op.drop_column("validation_runs", "archived_at")
