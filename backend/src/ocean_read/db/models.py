"""Database models."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ocean_read.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tenant (company). Projects join here for isolation."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(back_populates="projects")

    validation_schemas: Mapped[list["ValidationSchema"]] = relationship(
        back_populates="project",
        passive_deletes=True,
    )
    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        back_populates="project",
        passive_deletes=True,
    )


class ValidationSchema(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Versioned validation schema definition (JSON ``body``) per project.

    **Immutable versioning**: edits create a new row; prior active rows are archived.
    """

    __tablename__ = "validation_schemas"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    schema_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="validation_schemas")


class ValidationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One persisted outcome of POST ``/api/validate-document`` (audit trail + optional PDF replay)."""

    __tablename__ = "validation_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    validation_schema_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("validation_schemas.id", ondelete="SET NULL"),
        nullable=True,
    )
    schema_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    document_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pdf_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    snapshots: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    pdf_relative_path: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="validation_runs")
