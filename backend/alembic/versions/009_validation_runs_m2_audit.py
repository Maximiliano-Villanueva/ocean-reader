"""Add pdf_hash and pipeline snapshots to validation_runs (M2 auditability)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009_validation_runs_m2_audit"
down_revision: Union[str, Sequence[str], None] = "008_validation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("pdf_hash", sa.String(length=71), nullable=False, server_default=""),
    )
    op.add_column("validation_runs", sa.Column("snapshots", JSONB(), nullable=True))
    op.create_index("ix_validation_runs_pdf_hash", "validation_runs", ["pdf_hash"])
    op.create_index(
        "ix_validation_runs_project_schema_key",
        "validation_runs",
        ["project_id", "schema_key"],
    )
    op.create_index(
        "ix_validation_runs_project_outcome",
        "validation_runs",
        ["project_id", "outcome"],
    )
    op.alter_column("validation_runs", "pdf_hash", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_validation_runs_project_outcome", table_name="validation_runs")
    op.drop_index("ix_validation_runs_project_schema_key", table_name="validation_runs")
    op.drop_index("ix_validation_runs_pdf_hash", table_name="validation_runs")
    op.drop_column("validation_runs", "snapshots")
    op.drop_column("validation_runs", "pdf_hash")
