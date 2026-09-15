"""Unit tests for workspace seed helpers in ``scripts/ensure_default_validation.py``."""

from __future__ import annotations

import sys
from pathlib import Path

# Repo-root ``scripts/`` is not on PYTHONPATH during pytest.
_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ensure_default_validation import (  # noqa: E402
    DEFAULT_PROJECT_NAME,
    find_project_by_name,
    project_has_wine_default,
)


def test_find_project_by_name_matches_exact_name() -> None:
    projects = [{"id": "a", "name": "Other"}, {"id": "b", "name": DEFAULT_PROJECT_NAME}]
    found = find_project_by_name(projects, DEFAULT_PROJECT_NAME)
    assert found is not None
    assert found["id"] == "b"


def test_find_project_by_name_returns_none_when_missing() -> None:
    assert find_project_by_name([{"id": "a", "name": "Invoice demo"}], DEFAULT_PROJECT_NAME) is None


def test_project_has_wine_default_true_when_version_present() -> None:
    groups = [
        {
            "schema_key": "wine_quality",
            "versions": [{"version_label": "1.0"}, {"version_label": "2.0"}],
        }
    ]
    assert project_has_wine_default(groups) is True


def test_project_has_wine_default_false_for_other_keys_only() -> None:
    groups = [{"schema_key": "invoince", "versions": [{"version_label": "1.0"}]}]
    assert project_has_wine_default(groups) is False
