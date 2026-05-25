"""Round-trip tests for persisted pipeline snapshots (M2)."""

from __future__ import annotations

import json

from ocean_read.domain.validation.mapping import (
    AmbiguousFieldInfo,
    FieldEntry,
    InconsistencyReport,
)
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.domain.validation.snapshot_serializer import (
    deserialize_pipeline_snapshots,
    serialize_pipeline_snapshots,
)


def test_snapshot_roundtrip_json_preserves_structure() -> None:
    """serialize → JSON → deserialize yields JSON-equal payload."""

    blocks = [
        TextBlock(id="b0", page=1, bbox=(1.0, 2.0, 3.0, 4.0), text="pH: 3.4", section_label=None),
    ]
    candidates = [
        ExtractionCandidate(
            field="ph",
            value=3.4,
            source="regex",
            confidence=0.9,
            block_id="b0",
            page=1,
            evidence_text="pH: 3.4",
            bbox=(10.0, 20.0, 30.0, 40.0),
            section_label="Lab",
        ),
    ]
    field_map = {
        "ph": FieldEntry(status="found", candidates=tuple(candidates)),
        "alcohol": FieldEntry(status="missing", candidates=()),
    }
    inc = InconsistencyReport(has_ambiguity=False, ambiguous_fields=())
    resolved = {"ph": 3.4}

    raw = serialize_pipeline_snapshots(
        blocks=blocks,
        candidates=candidates,
        field_map=field_map,
        inconsistency=inc,
        resolved_document=resolved,
    )
    blob = json.dumps(raw)
    loaded = json.loads(blob)
    restored = deserialize_pipeline_snapshots(loaded)
    assert restored == loaded
    assert restored["blocks"][0]["id"] == "b0"
    assert restored["resolved_document"]["ph"] == 3.4


def test_snapshot_ambiguity_serializes_ambiguous_fields() -> None:
    """InconsistencyReport with ambiguous_fields survives JSON round-trip."""

    c1 = ExtractionCandidate(
        field="ph",
        value=3.1,
        source="regex",
        confidence=0.5,
        block_id="b1",
        page=1,
        evidence_text="pH: 3.1",
    )
    c2 = ExtractionCandidate(
        field="ph",
        value=4.2,
        source="regex",
        confidence=0.5,
        block_id="b2",
        page=1,
        evidence_text="pH: 4.2",
    )
    amb = AmbiguousFieldInfo(field="ph", count=2, candidates=(c1, c2))
    inc = InconsistencyReport(has_ambiguity=True, ambiguous_fields=(amb,))
    raw = serialize_pipeline_snapshots(
        blocks=[],
        candidates=[c1, c2],
        field_map={"ph": FieldEntry(status="ambiguous", candidates=(c1, c2))},
        inconsistency=inc,
        resolved_document={},
    )
    loaded = json.loads(json.dumps(raw))
    out = deserialize_pipeline_snapshots(loaded)
    assert out["inconsistency_report"]["has_ambiguity"] is True
    assert len(out["inconsistency_report"]["ambiguous_fields"]) == 1
    assert out["inconsistency_report"]["ambiguous_fields"][0]["field"] == "ph"
