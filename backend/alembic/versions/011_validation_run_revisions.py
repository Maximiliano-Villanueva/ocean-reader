"""Add parent_run_id and revision_number for manual correction revisions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "011_validation_run_revisions"
down_revision: Union[str, Sequence[str], None] = "010_validation_runs_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("parent_run_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "validation_runs",
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_foreign_key(
        "fk_validation_runs_parent_run_id",
        "validation_runs",
        "validation_runs",
        ["parent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_validation_runs_parent_run_id",
        "validation_runs",
        ["parent_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_parent_run_id", table_name="validation_runs")
    op.drop_constraint("fk_validation_runs_parent_run_id", "validation_runs", type_="foreignkey")
    op.drop_column("validation_runs", "revision_number")
    op.drop_column("validation_runs", "parent_run_id")
