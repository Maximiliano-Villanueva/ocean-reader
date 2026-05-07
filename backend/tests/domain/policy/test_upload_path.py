"""TDD: upload path policy (Ocean Read — artifact storage safety)."""

from pathlib import Path

import pytest

from ocean_read.domain.policy.upload_path import PathEscapeError, path_must_be_under, safe_upload_leaf


def test_safe_upload_leaf_strips_directory_components() -> None:
    assert safe_upload_leaf("../../etc/passwd") == "passwd"
    assert safe_upload_leaf("nested/file.pdf") == "file.pdf"


def test_safe_upload_leaf_empty_becomes_default() -> None:
    assert safe_upload_leaf("") == "file.bin"


def test_path_must_be_under_accepts_descendant(tmp_path: Path) -> None:
    root = tmp_path / "ocean"
    root.mkdir()
    child = root / "nested" / "f.pdf"
    child.parent.mkdir(parents=True)
    child.write_bytes(b"x")
    path_must_be_under(root=root, candidate=child)


def test_path_must_be_under_rejects_escape(tmp_path: Path) -> None:
    root = tmp_path / "ocean"
    root.mkdir()
    evil = tmp_path / "breakout"
    evil.mkdir()
    with pytest.raises(PathEscapeError):
        path_must_be_under(root=root, candidate=evil / "x.bin")
