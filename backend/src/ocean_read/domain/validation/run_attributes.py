"""
Normalize and match user-defined attributes on validation runs.

Attributes are stored as ``{key: value}`` where ``value`` may be ``None`` for key-only tags
(e.g. ``{"batch": "March AP", "fixture": None}``).
"""

from __future__ import annotations

from typing import Any, Mapping


def normalize_run_attributes(raw: Any) -> dict[str, str | None]:
    """
    Parse API/upload input into a canonical attribute map.

    Accepts a JSON object or a list of ``{"key": "...", "value": "..."}`` entries.
    Empty keys are dropped. Duplicate keys keep the last value.
    """

    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        out: dict[str, str | None] = {}
        for key, value in raw.items():
            k = str(key).strip()
            if not k:
                continue
            if value is None:
                out[k] = None
            else:
                v = str(value).strip()
                out[k] = v if v else None
        return out
    if isinstance(raw, list):
        out: dict[str, str | None] = {}
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            k = str(item.get("key", "")).strip()
            if not k:
                continue
            value = item.get("value")
            if value is None:
                out[k] = None
            else:
                v = str(value).strip()
                out[k] = v if v else None
        return out
    return {}


def run_attributes_match(
    run_attributes: Mapping[str, str | None],
    required: list[Mapping[str, Any]],
) -> bool:
    """Return True when every required attribute filter matches the run."""

    for req in required:
        key = str(req.get("key", "")).strip()
        if not key:
            continue
        if key not in run_attributes:
            return False
        expected = req.get("value")
        if expected is None:
            continue
        actual = run_attributes.get(key)
        if actual is None or str(actual) != str(expected).strip():
            return False
    return True


def merge_attribute_vocabularies(
    left: Mapping[str, set[str]],
    right: Mapping[str, set[str]],
) -> dict[str, list[str]]:
    """Merge project attribute vocabularies (sorted unique values per key)."""

    keys = set(left.keys()) | set(right.keys())
    out: dict[str, list[str]] = {}
    for key in sorted(keys):
        values = set(left.get(key, set())) | set(right.get(key, set()))
        out[key] = sorted(v for v in values if v)
    return out
