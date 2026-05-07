"""Liveness / build metadata."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ocean_read.config import get_settings

router = APIRouter(tags=["System"])


@router.get("/health")
async def health() -> dict[str, Any]:
    cfg = get_settings()
    return {
        "ok": True,
        "service": "ocean-read",
        "llm_model": cfg.llm_model,
        "embedding_dimension": cfg.embedding_dimension,
    }
