"""Filesystem policy for user-provided upload names and stored paths."""

from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    """Candidate path resolves outside the trusted upload root."""


def safe_upload_leaf(name: str) -> str:
    """Single path component for storage keys; strips traversal."""
    cleaned = Path(name).name.replace("..", "").replace("/", "_")
    return cleaned[:255] if cleaned else "file.bin"


def path_must_be_under(*, root: Path, candidate: Path) -> None:
    root_r = root.resolve()
    try:
        candidate.resolve().relative_to(root_r)
    except Exception as e:
        raise PathEscapeError(str(e)) from e
