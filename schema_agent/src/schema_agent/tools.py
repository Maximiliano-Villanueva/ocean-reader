"""
Internal tools for the schema authoring agent (capabilities, validate, patch).
"""

from __future__ import annotations

import json
import os
from importlib import resources
from typing import Any

import httpx


def get_engine_capabilities() -> dict[str, Any]:
    """Return machine-readable strict-engine capabilities for the agent."""

    raw = resources.files("schema_agent").joinpath("capabilities_manifest.json").read_text(encoding="utf-8")
    return json.loads(raw)


def validate_schema_body(body: dict[str, Any]) -> dict[str, Any]:
    """Validate draft schema via Ocean Read backend DSL checker."""

    base = os.environ.get("OCEAN_BACKEND_URL", "http://backend:8000").rstrip("/")
    r = httpx.post(f"{base}/api/internal/validate-schema-body", json={"body": body}, timeout=60.0)
    r.raise_for_status()
    return r.json()


def apply_schema_patch(body: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge top-level keys from ``patch`` into ``body``."""

    out = dict(body)
    for key, val in patch.items():
        if key == "fields" and isinstance(val, dict) and isinstance(out.get("fields"), dict):
            merged = dict(out["fields"])
            merged.update(val)
            out["fields"] = merged
        elif key == "open_ended" and isinstance(val, dict) and isinstance(out.get("open_ended"), dict):
            merged = dict(out["open_ended"])
            merged.update(val)
            out["open_ended"] = merged
        else:
            out[key] = val
    return out
