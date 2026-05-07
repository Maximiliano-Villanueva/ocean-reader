"""Validation schema persistence port."""

from __future__ import annotations

import uuid
from typing import Any, Protocol


class ValidationSchemaRepository(Protocol):
    """Hexagonal port — implemented by SQLAlchemy adapter."""

    async def create_version(
        self,
        *,
        project_id: uuid.UUID,
        schema_key: str,
        version_label: str,
        body: dict[str, Any],
        archive_previous_active: bool = True,
    ) -> uuid.UUID:
        """Insert a new schema row (immutable version). Optionally archive prior **active** row."""

    async def archive(self, schema_id: uuid.UUID) -> None:
        """Mark row archived (not eligible for validation)."""

    async def soft_delete(self, schema_id: uuid.UUID) -> None:
        """Logical delete — excluded from validation and default listings."""

    async def get_active(self, project_id: uuid.UUID, schema_key: str) -> dict[str, Any] | None:
        """Return ``body`` + metadata for the active schema, or ``None``."""

    async def list_versions(self, project_id: uuid.UUID, schema_key: str) -> list[dict[str, Any]]:
        """All versions for audit (includes archived; excludes soft-deleted)."""

    async def get_by_version(
        self,
        project_id: uuid.UUID,
        schema_key: str,
        version_label: str,
    ) -> dict[str, Any] | None:
        """Return ``body`` + metadata for an exact version (active or archived); excludes soft-deleted."""

    async def list_grouped_by_project(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        """UI: ``schema_key`` groups with nested version rows (non-deleted only)."""

    async def get_by_id(self, schema_id: uuid.UUID) -> dict[str, Any] | None:
        """Return one non-deleted row by primary key, or ``None``."""
