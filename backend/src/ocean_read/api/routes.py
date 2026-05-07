"""Aggregates HTTP routers under ``/api`` (validation engine + workspace shell)."""

from __future__ import annotations

from fastapi import APIRouter

from ocean_read.api.routers import logs, system, validation, workspace

router = APIRouter(prefix="/api")

router.include_router(system.router)
router.include_router(workspace.router)
router.include_router(validation.router)
router.include_router(logs.router)
