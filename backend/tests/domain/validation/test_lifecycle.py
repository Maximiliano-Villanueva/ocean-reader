"""Schema lifecycle rules."""

from ocean_read.domain.validation.lifecycle import SchemaLifecycleStatus, can_use_for_validation


def test_only_active_usable() -> None:
    assert can_use_for_validation(SchemaLifecycleStatus.ACTIVE)
    assert not can_use_for_validation(SchemaLifecycleStatus.ARCHIVED)
    assert not can_use_for_validation(SchemaLifecycleStatus.DELETED)
