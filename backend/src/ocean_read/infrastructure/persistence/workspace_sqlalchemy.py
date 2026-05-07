"""SQLAlchemy adapter for :class:`~ocean_read.application.ports.workspace.WorkspaceRepository`."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ocean_read.db.models import Project


class SqlAlchemyWorkspaceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_project(self, project_id: uuid.UUID) -> Project | None:
        return (await self._db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()

    async def list_projects(self) -> list[Project]:
        q = await self._db.execute(select(Project).order_by(Project.created_at.desc()))
        return list(q.scalars().all())

    async def add_project(self, project: Project) -> None:
        self._db.add(project)

    async def delete_project_entity(self, project: Project) -> None:
        await self._db.delete(project)

    async def commit_refresh(self, *entities: object) -> None:
        await self._db.commit()
        for e in entities:
            await self._db.refresh(e)
