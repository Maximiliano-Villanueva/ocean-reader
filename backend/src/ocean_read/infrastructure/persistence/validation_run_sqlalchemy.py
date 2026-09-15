"""SQLAlchemy adapter for persisted validation run rows (M1 audit trail + M2 lifecycle)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ocean_read.db.models import ValidationRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _escape_ilike_literal(text: str) -> str:
    """Escape ``%`` and ``_`` for SQL ``ILIKE`` with backslash escape."""

    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlAlchemyValidationRunRepository:
    """List and load ``validation_runs`` for a project with offset pagination."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _apply_visibility(stmt, *, include_hidden: bool):
        """Default list shows only runs that are neither archived nor soft-deleted."""

        if include_hidden:
            return stmt
        return stmt.where(
            ValidationRun.archived_at.is_(None),
            ValidationRun.deleted_at.is_(None),
        )

    @staticmethod
    def _apply_run_filters(
        stmt,
        *,
        schema_key: str | None = None,
        version_label: str | None = None,
        outcome: str | None = None,
        document_contains: str | None = None,
    ):
        """Optional list filters for validation history."""

        if schema_key:
            stmt = stmt.where(ValidationRun.schema_key == schema_key)
        if version_label:
            stmt = stmt.where(ValidationRun.version_label == version_label)
        if outcome:
            stmt = stmt.where(ValidationRun.outcome == outcome)
        needle = (document_contains or "").strip()
        if needle:
            pattern = f"%{_escape_ilike_literal(needle)}%"
            stmt = stmt.where(ValidationRun.document_filename.ilike(pattern, escape="\\"))
        return stmt

    async def count_for_project(
        self,
        project_id: uuid.UUID,
        *,
        schema_key: str | None = None,
        version_label: str | None = None,
        outcome: str | None = None,
        document_contains: str | None = None,
        include_hidden: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(ValidationRun).where(ValidationRun.project_id == project_id)
        stmt = self._apply_visibility(stmt, include_hidden=include_hidden)
        stmt = self._apply_run_filters(
            stmt,
            schema_key=schema_key,
            version_label=version_label,
            outcome=outcome,
            document_contains=document_contains,
        )
        q = await self._session.execute(stmt)
        n = q.scalar()
        return int(n or 0)

    async def list_page(
        self,
        project_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
        schema_key: str | None = None,
        version_label: str | None = None,
        outcome: str | None = None,
        document_contains: str | None = None,
        include_hidden: bool = False,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.project_id == project_id)
            .order_by(ValidationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        stmt = self._apply_visibility(stmt, include_hidden=include_hidden)
        stmt = self._apply_run_filters(
            stmt,
            schema_key=schema_key,
            version_label=version_label,
            outcome=outcome,
            document_contains=document_contains,
        )
        q = await self._session.execute(stmt)
        rows = q.scalars().all()
        return [_run_summary_dict(r) for r in rows]

    async def get(self, project_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        q = await self._session.execute(
            select(ValidationRun).where(ValidationRun.project_id == project_id, ValidationRun.id == run_id)
        )
        r = q.scalar_one_or_none()
        if r is None:
            return None
        return {
            "id": str(r.id),
            "project_id": str(r.project_id),
            "validation_schema_id": str(r.validation_schema_id) if r.validation_schema_id else None,
            "schema_key": r.schema_key,
            "version_label": r.version_label,
            "document_filename": r.document_filename,
            "outcome": r.outcome,
            "report": dict(r.report),
            "pdf_relative_path": r.pdf_relative_path,
            "pdf_hash": r.pdf_hash,
            "snapshots": dict(r.snapshots) if r.snapshots is not None else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "archived_at": r.archived_at.isoformat() if r.archived_at else None,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            "parent_run_id": str(r.parent_run_id) if r.parent_run_id else None,
            "revision_number": int(r.revision_number or 1),
            "attributes": dict(r.attributes or {}),
        }

    async def insert(
        self,
        *,
        run_id: uuid.UUID,
        project_id: uuid.UUID,
        validation_schema_id: uuid.UUID | None,
        schema_key: str,
        version_label: str,
        document_filename: str,
        outcome: str,
        report: dict[str, Any],
        pdf_hash: str,
        snapshots: dict[str, Any] | None,
        pdf_relative_path: str | None,
        parent_run_id: uuid.UUID | None = None,
        revision_number: int = 1,
        attributes: dict[str, str | None] | None = None,
    ) -> uuid.UUID:
        row = ValidationRun(
            id=run_id,
            project_id=project_id,
            validation_schema_id=validation_schema_id,
            schema_key=schema_key,
            version_label=version_label,
            document_filename=document_filename,
            outcome=outcome,
            report=report,
            pdf_hash=pdf_hash,
            snapshots=snapshots,
            pdf_relative_path=pdf_relative_path,
            parent_run_id=parent_run_id,
            revision_number=revision_number,
            attributes=dict(attributes or {}),
        )
        self._session.add(row)
        await self._session.flush()
        return run_id

    async def soft_delete(self, project_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Set ``deleted_at`` (idempotent if already set)."""

        stmt = (
            update(ValidationRun)
            .where(
                ValidationRun.project_id == project_id,
                ValidationRun.id == run_id,
            )
            .values(deleted_at=_utcnow())
        )
        res = await self._session.execute(stmt)
        return res.rowcount > 0

    async def set_archived(self, project_id: uuid.UUID, run_id: uuid.UUID, *, archived: bool) -> bool:
        """Set or clear ``archived_at``."""

        ts = _utcnow() if archived else None
        stmt = (
            update(ValidationRun)
            .where(ValidationRun.project_id == project_id, ValidationRun.id == run_id)
            .values(archived_at=ts)
        )
        res = await self._session.execute(stmt)
        return res.rowcount > 0

    async def restore(self, project_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Clear archive and soft-delete timestamps (audit recovery)."""

        stmt = (
            update(ValidationRun)
            .where(ValidationRun.project_id == project_id, ValidationRun.id == run_id)
            .values(archived_at=None, deleted_at=None)
        )
        res = await self._session.execute(stmt)
        return res.rowcount > 0

    async def get_lifecycle_state(self, project_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any] | None:
        result = await self._session.execute(
            select(ValidationRun.archived_at, ValidationRun.deleted_at).where(
                ValidationRun.project_id == project_id,
                ValidationRun.id == run_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            return None
        arch, deleted = row[0], row[1]
        return {
            "archived_at": arch.isoformat() if arch else None,
            "deleted_at": deleted.isoformat() if deleted else None,
        }


def _run_summary_dict(r: ValidationRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "schema_key": r.schema_key,
        "version_label": r.version_label,
        "document_filename": r.document_filename,
        "outcome": r.outcome,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "archived_at": r.archived_at.isoformat() if r.archived_at else None,
        "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
        "parent_run_id": str(r.parent_run_id) if r.parent_run_id else None,
        "revision_number": int(r.revision_number or 1),
        "attributes": dict(r.attributes or {}),
    }
