"""Projects — long-lived containers for validation schemas."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from ocean_read.api.deps import WorkspaceSvcDep
from ocean_read.db.models import Project
from ocean_read.schemas import ProjectCreate, ProjectRead

router = APIRouter(tags=["Workspace"])


@router.post("/projects", response_model=ProjectRead)
async def create_project(body: ProjectCreate, svc: WorkspaceSvcDep) -> Project:
    return await svc.create_project(body.name)


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(svc: WorkspaceSvcDep) -> list[Project]:
    return await svc.list_projects()


@router.delete("/projects/{project_id}")
async def delete_project(project_id: uuid.UUID, svc: WorkspaceSvcDep) -> dict[str, str]:
    await svc.delete_project(project_id)
    return {"status": "deleted"}
