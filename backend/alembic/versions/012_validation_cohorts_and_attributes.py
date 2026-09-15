"""Add run attributes JSONB and validation_cohorts for Insights tab."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "012_cohort_attributes"
down_revision: Union[str, Sequence[str], None] = "011_validation_run_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("attributes", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "ix_validation_runs_attributes",
        "validation_runs",
        ["attributes"],
        postgresql_using="gin",
    )

    op.create_table(
        "validation_cohorts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("filters", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pass_threshold_pct", sa.Float(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_validation_cohorts_project_id", "validation_cohorts", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_validation_cohorts_project_id", table_name="validation_cohorts")
    op.drop_table("validation_cohorts")
    op.drop_index("ix_validation_runs_attributes", table_name="validation_runs")
    op.drop_column("validation_runs", "attributes")
