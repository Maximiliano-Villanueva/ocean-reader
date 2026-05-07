"""Persist validation run history (audit + optional PDF replay path)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008_validation_runs"
down_revision: Union[str, Sequence[str], None] = "007_drop_user_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("validation_schema_id", UUID(as_uuid=True), nullable=True),
        sa.Column("schema_key", sa.String(length=128), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("document_filename", sa.String(length=1024), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("report", JSONB, nullable=False),
        sa.Column("pdf_relative_path", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["validation_schema_id"], ["validation_schemas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_runs_project_created_at",
        "validation_runs",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_project_created_at", table_name="validation_runs")
    op.drop_table("validation_runs")
