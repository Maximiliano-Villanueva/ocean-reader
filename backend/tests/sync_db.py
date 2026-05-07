"""Synchronous Postgres helpers for tests (pairs with_starlette synchronous TestClient_)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def sync_engine_from_settings() -> Engine:
    from ocean_read.config import get_settings

    url = get_settings().database_url
    if url.startswith("postgresql+asyncpg://"):
        sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    else:
        sync_url = url
    return create_engine(sync_url)


def exec_sync(sql: str, params: Mapping[str, Any] | None = None) -> None:
    eng = sync_engine_from_settings()
    try:
        with eng.connect() as conn:
            conn.execute(text(sql), dict(params or {}))
            conn.commit()
    finally:
        eng.dispose()


def fetch_scalar(sql: str, params: Mapping[str, Any] | None = None) -> Any:
    eng = sync_engine_from_settings()
    try:
        with eng.connect() as conn:
            return conn.execute(text(sql), dict(params or {})).scalar_one()
    finally:
        eng.dispose()
