"""SQLAlchemy adapter for persisted validation run rows (M1 audit trail)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ocean_read.db.models import ValidationRun


class SqlAlchemyValidationRunRepository:
    """List and load ``validation_runs`` for a project with offset pagination."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_for_project(self, project_id: uuid.UUID) -> int:
        q = await self._session.execute(
            select(func.count()).select_from(ValidationRun).where(ValidationRun.project_id == project_id)
        )
        n = q.scalar()
        return int(n or 0)

    async def list_page(
        self, project_id: uuid.UUID, *, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        q = await self._session.execute(
            select(ValidationRun)
            .where(ValidationRun.project_id == project_id)
            .order_by(ValidationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = q.scalars().all()
        return [
            {
                "id": str(r.id),
                "schema_key": r.schema_key,
                "version_label": r.version_label,
                "document_filename": r.document_filename,
                "outcome": r.outcome,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

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
            "schema_key": r.schema_key,
            "version_label": r.version_label,
            "document_filename": r.document_filename,
            "outcome": r.outcome,
            "report": dict(r.report),
            "pdf_relative_path": r.pdf_relative_path,
            "created_at": r.created_at.isoformat() if r.created_at else None,
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
        pdf_relative_path: str | None,
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
            pdf_relative_path=pdf_relative_path,
        )
        self._session.add(row)
        await self._session.flush()
        return run_id
