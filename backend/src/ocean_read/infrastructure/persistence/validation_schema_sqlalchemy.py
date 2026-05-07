"""SQLAlchemy adapter for :class:`~ocean_read.application.ports.validation_schema_repository.ValidationSchemaRepository`."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from ocean_read.application.ports.validation_schema_repository import ValidationSchemaRepository
from ocean_read.db.models import ValidationSchema
from ocean_read.domain.validation.lifecycle import SchemaLifecycleStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlAlchemyValidationSchemaRepository:
    """Async persistence for versioned validation schemas."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def create_version(
        self,
        *,
        project_id: uuid.UUID,
        schema_key: str,
        version_label: str,
        body: dict[str, Any],
        archive_previous_active: bool = True,
    ) -> uuid.UUID:
        if archive_previous_active:
            await self._session.execute(
                update(ValidationSchema)
                .where(
                    ValidationSchema.project_id == project_id,
                    ValidationSchema.schema_key == schema_key,
                    ValidationSchema.status == SchemaLifecycleStatus.ACTIVE.value,
                    ValidationSchema.deleted_at.is_(None),
                )
                .values(
                    status=SchemaLifecycleStatus.ARCHIVED.value,
                    archived_at=_utcnow(),
                )
            )

        row = ValidationSchema(
            project_id=project_id,
            schema_key=schema_key,
            version_label=version_label,
            status=SchemaLifecycleStatus.ACTIVE.value,
            body=body,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def get_by_id(self, schema_id: uuid.UUID) -> dict[str, Any] | None:
        q = await self._session.execute(
            select(ValidationSchema).where(
                ValidationSchema.id == schema_id,
                ValidationSchema.deleted_at.is_(None),
            )
        )
        row = q.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "project_id": row.project_id,
            "schema_key": row.schema_key,
            "version_label": row.version_label,
            "status": row.status,
            "body": dict(row.body),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def archive(self, schema_id: uuid.UUID) -> None:
        await self._session.execute(
            update(ValidationSchema)
            .where(ValidationSchema.id == schema_id, ValidationSchema.deleted_at.is_(None))
            .values(status=SchemaLifecycleStatus.ARCHIVED.value, archived_at=_utcnow())
        )

    async def soft_delete(self, schema_id: uuid.UUID) -> None:
        await self._session.execute(
            update(ValidationSchema)
            .where(ValidationSchema.id == schema_id)
            .values(status=SchemaLifecycleStatus.DELETED.value, deleted_at=_utcnow())
        )

    async def get_active(self, project_id: uuid.UUID, schema_key: str) -> dict[str, Any] | None:
        q = await self._session.execute(
            select(ValidationSchema)
            .where(
                ValidationSchema.project_id == project_id,
                ValidationSchema.schema_key == schema_key,
                ValidationSchema.status == SchemaLifecycleStatus.ACTIVE.value,
                ValidationSchema.deleted_at.is_(None),
            )
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "schema_key": row.schema_key,
            "version_label": row.version_label,
            "status": row.status,
            "body": dict(row.body),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def list_versions(self, project_id: uuid.UUID, schema_key: str) -> list[dict[str, Any]]:
        q = await self._session.execute(
            select(ValidationSchema)
            .where(
                ValidationSchema.project_id == project_id,
                ValidationSchema.schema_key == schema_key,
                ValidationSchema.deleted_at.is_(None),
            )
            .order_by(ValidationSchema.created_at.asc())
        )
        rows = q.scalars().all()
        return [
            {
                "id": str(r.id),
                "version_label": r.version_label,
                "status": r.status,
                "archived_at": r.archived_at.isoformat() if r.archived_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def get_by_version(
        self,
        project_id: uuid.UUID,
        schema_key: str,
        version_label: str,
    ) -> dict[str, Any] | None:
        q = await self._session.execute(
            select(ValidationSchema)
            .where(
                ValidationSchema.project_id == project_id,
                ValidationSchema.schema_key == schema_key,
                ValidationSchema.version_label == version_label,
                ValidationSchema.deleted_at.is_(None),
            )
            .limit(1)
        )
        row = q.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "schema_key": row.schema_key,
            "version_label": row.version_label,
            "status": row.status,
            "body": dict(row.body),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def list_grouped_by_project(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        q = await self._session.execute(
            select(ValidationSchema)
            .where(
                ValidationSchema.project_id == project_id,
                ValidationSchema.deleted_at.is_(None),
            )
            .order_by(ValidationSchema.schema_key.asc(), ValidationSchema.created_at.asc())
        )
        rows = q.scalars().all()
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(r.schema_key, []).append(
                {
                    "id": str(r.id),
                    "version_label": r.version_label,
                    "status": r.status,
                    "archived_at": r.archived_at.isoformat() if r.archived_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return [{"schema_key": k, "versions": groups[k]} for k in sorted(groups.keys())]


def validation_schema_repository(session: Any) -> ValidationSchemaRepository:
    """Factory for DI."""

    return SqlAlchemyValidationSchemaRepository(session)
