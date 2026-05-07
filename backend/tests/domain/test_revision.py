"""Tests for revision label suggestion."""

import pytest

from ocean_read.domain.validation.revision import suggest_next_version_label


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        ([], "1.0"),
        (["1.0"], "1.1"),
        (["1.0", "1.1"], "1.2"),
        (["0.9", "1.0"], "1.1"),
        (["foo", "bar"], "rev-3"),
    ],
)
def test_suggest_next_version_label(existing: list[str], expected: str) -> None:
    assert suggest_next_version_label(existing) == expected
