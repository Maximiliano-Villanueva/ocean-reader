"""Organizations + corpus knowledge_scope (multitenancy prelude)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002_org_scope"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = "00000000-0000-4000-8000-000000000001"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name) "
            f"SELECT '{DEFAULT_ORG_ID}'::uuid, 'Default organization' "
            "WHERE NOT EXISTS (SELECT 1 FROM organizations o WHERE o.id = "
            f"'{DEFAULT_ORG_ID}'::uuid)"
        ),
    )

    op.add_column(
        "projects",
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            f"UPDATE projects SET organization_id = '{DEFAULT_ORG_ID}'::uuid "
            "WHERE organization_id IS NULL"
        ),
    )
    op.alter_column(
        "projects",
        "organization_id",
        nullable=False,
        server_default=sa.text(f"'{DEFAULT_ORG_ID}'::uuid"),
    )
    op.create_foreign_key(
        "fk_projects_organization_id",
        "projects",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    op.add_column(
        "documents",
        sa.Column(
            "knowledge_scope",
            sa.String(length=32),
            nullable=False,
            server_default="company",
        ),
    )
    op.add_column("documents", sa.Column("owner_principal_id", UUID(as_uuid=True), nullable=True))
    op.create_check_constraint(
        "ck_documents_knowledge_owner",
        "documents",
        sa.text(
            "(knowledge_scope = 'company' AND owner_principal_id IS NULL) OR "
            "(knowledge_scope = 'user_private' AND owner_principal_id IS NOT NULL)"
        ),
    )
    op.create_index("ix_documents_project_checksum", "documents", ["project_id", "checksum"])


def downgrade() -> None:
    op.drop_index("ix_documents_project_checksum", table_name="documents")
    op.drop_constraint("ck_documents_knowledge_owner", "documents", type_="check")
    op.drop_column("documents", "owner_principal_id")
    op.drop_column("documents", "knowledge_scope")

    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_constraint("fk_projects_organization_id", "projects", type_="foreignkey")
    op.drop_column("projects", "organization_id")

    op.drop_table("organizations")
