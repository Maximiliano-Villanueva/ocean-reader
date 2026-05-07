"""Lifecycle states for persisted validation schemas."""

from __future__ import annotations

from enum import Enum


class SchemaLifecycleStatus(str, Enum):
    """Persisted on ``ValidationSchema.status``."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


def can_use_for_validation(status: str | SchemaLifecycleStatus) -> bool:
    """Only **active** schemas may drive validation jobs."""

    s = status.value if isinstance(status, SchemaLifecycleStatus) else str(status)
    return s == SchemaLifecycleStatus.ACTIVE.value
