"""Tests for validation run attribute normalization and matching."""

from __future__ import annotations

from ocean_read.domain.validation.run_attributes import (
    merge_attribute_vocabularies,
    normalize_run_attributes,
    run_attributes_match,
)


def test_normalize_run_attributes_from_dict() -> None:
    raw = {"batch": "March AP", "region": "US", "reviewed": None}
    assert normalize_run_attributes(raw) == {"batch": "March AP", "region": "US", "reviewed": None}


def test_normalize_run_attributes_from_list_of_pairs() -> None:
    raw = [{"key": "batch", "value": "Q1"}, {"key": "fixture"}]
    assert normalize_run_attributes(raw) == {"batch": "Q1", "fixture": None}


def test_normalize_run_attributes_rejects_invalid() -> None:
    assert normalize_run_attributes(None) == {}
    assert normalize_run_attributes("bad") == {}
    assert normalize_run_attributes({"": "x"}) == {}


def test_run_attributes_match_key_and_value() -> None:
    attrs = {"batch": "March AP", "vendor": "Acme"}
    assert run_attributes_match(attrs, [{"key": "batch", "value": "March AP"}])
    assert not run_attributes_match(attrs, [{"key": "batch", "value": "April AP"}])


def test_run_attributes_match_key_only() -> None:
    attrs = {"fixture": None, "batch": "Q1"}
    assert run_attributes_match(attrs, [{"key": "fixture"}])
    assert not run_attributes_match(attrs, [{"key": "missing"}])


def test_merge_attribute_vocabularies() -> None:
    merged = merge_attribute_vocabularies(
        {"batch": {"Q1", "Q2"}, "fixture": set()},
        {"batch": {"Q2", "Q3"}, "region": {"US"}},
    )
    assert merged["batch"] == ["Q1", "Q2", "Q3"]
    assert merged["fixture"] == []
    assert merged["region"] == ["US"]
