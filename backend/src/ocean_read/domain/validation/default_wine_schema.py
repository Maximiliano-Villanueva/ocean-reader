"""Canonical M1 wine-quality schema body — seeded for new projects and optional API default."""

from __future__ import annotations

from typing import Any

# Mirrors ``backend/tests/fixtures/wine/schema.json`` (kept in code so Docker/runtime never reads the test tree).
DEFAULT_WINE_QUALITY_SCHEMA_BODY: dict[str, Any] = {
    "fields": {
        "ph": {
            "type": "number",
            "required": True,
            "min": 2.5,
            "max": 4.5,
            "aliases": ["pH", "Measured pH", "pH level", "ph value"],
        },
        "alcohol": {
            "type": "number",
            "required": True,
            "min": 8.0,
            "max": 15.0,
            "aliases": ["Alcohol", "Alcohol %", "Alcohol content", "EtOH", "Alc."],
        },
        "quality": {
            "type": "number",
            "required": True,
            "min": 0,
            "max": 10,
            "aliases": ["Quality", "Quality score", "Panel rating"],
        },
    },
    "rules": ["required", "range_validation", "type_check"],
}

DEFAULT_WINE_SCHEMA_KEY = "wine_quality"
DEFAULT_WINE_VERSION_LABEL = "1.0"
