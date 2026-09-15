"""
LLM judge for non-regex extraction winners.

When enabled, the pipeline asks the model whether a layout/LLM/vision pick matches the
field spec and PDF evidence. Rejected picks are removed; the field becomes ambiguous or missing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from ocean_read.domain.validation.mapping import FieldEntry
from ocean_read.domain.validation.mapping import _values_equivalent  # noqa: PLC2701 — shared equivalence
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import (
    ExtractionCandidate,
    resolve_field_candidate,
)

logger = logging.getLogger(__name__)

_REGEX_SOURCES = frozenset({"regex"})


@dataclass(frozen=True)
class ExtractionJudgeNote:
    """Audit note for one judged field."""

    field: str
    approved: bool
    source: str
    value: Any
    reason: str


def judge_enabled_for_schema(schema_body: dict[str, Any], *, settings_enabled: bool) -> bool:
    """Global settings plus optional ``extraction.judge_non_regex`` (default True when settings on)."""

    if not settings_enabled:
        return False
    extraction = schema_body.get("extraction")
    if not isinstance(extraction, dict):
        return True
    flag = extraction.get("judge_non_regex")
    if flag is None:
        return True
    return bool(flag)


def _field_wants_judge(spec: dict[str, Any]) -> bool:
    if spec.get("llm_judge") is False:
        return False
    return True


async def _judge_one(
    field: str,
    candidate: ExtractionCandidate,
    spec: dict[str, Any],
    blocks: list[TextBlock],
    *,
    client: Any,
) -> tuple[bool, str]:
    """Return (approved, reason) from the LLM."""

    doc_excerpt = "\n".join(b.text for b in blocks[:80])[:12000]
    aliases = spec.get("aliases") or []
    typ = spec.get("type", "string")
    system = (
        "You verify PDF field extractions. Reply with JSON only: "
        '{"approved": true|false, "reason": "short explanation"}. '
        "Approve when the value clearly matches the field definition and evidence. "
        "Reject when the value is wrong, from the wrong section, or not supported by the text."
    )
    user = (
        f"Field: {field}\nType: {typ}\nLabels: {', '.join(str(a) for a in aliases[:8])}\n"
        f"Extracted value: {candidate.value!r}\nSource: {candidate.source}\n"
        f"Evidence snippet: {candidate.evidence_text!r}\n\nDocument text:\n{doc_excerpt}\n"
    )
    try:
        raw = await client.complete(system, user, temperature=0.0)
        data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        if isinstance(data, dict):
            approved = bool(data.get("approved"))
            reason = str(data.get("reason") or "").strip()[:500]
            return approved, reason or ("ok" if approved else "rejected")
    except Exception as exc:
        logger.info("Extraction judge skipped for %s: %s", field, exc)
    return True, "judge_unavailable"


def _rebuild_entry_after_rejection(
    field: str,
    remaining: list[ExtractionCandidate],
) -> FieldEntry:
    if not remaining:
        return FieldEntry(status="missing", candidates=())
    unique_vals: list[Any] = []
    for c in remaining:
        if not any(_values_equivalent(c.value, u) for u in unique_vals):
            unique_vals.append(c.value)
    if len(unique_vals) > 1:
        return FieldEntry(status="ambiguous", candidates=tuple(remaining))
    return FieldEntry(status="found", candidates=tuple(remaining))


async def apply_extraction_judge(
    field_map: dict[str, FieldEntry],
    schema_fields: dict[str, Any],
    schema_body: dict[str, Any],
    blocks: list[TextBlock],
    *,
    client: Any,
    enabled: bool,
) -> tuple[dict[str, FieldEntry], tuple[ExtractionJudgeNote, ...]]:
    """
    Judge non-regex winners; mutate ``field_map`` when the model rejects a pick.

    Regex extractions are trusted and never judged.
    """

    if not enabled or not judge_enabled_for_schema(schema_body, settings_enabled=True):
        return field_map, ()

    out: dict[str, FieldEntry] = dict(field_map)
    notes: list[ExtractionJudgeNote] = []

    for fname, entry in field_map.items():
        if entry.status != "found" or not entry.candidates:
            out[fname] = entry
            continue
        spec = schema_fields.get(fname)
        if not isinstance(spec, dict):
            spec = {}
        if not _field_wants_judge(spec):
            out[fname] = entry
            continue
        try:
            winner = resolve_field_candidate(fname, list(entry.candidates))
        except ValueError:
            out[fname] = entry
            continue
        if winner.source.lower() in _REGEX_SOURCES:
            out[fname] = entry
            continue

        approved, reason = await _judge_one(fname, winner, spec, blocks, client=client)
        notes.append(
            ExtractionJudgeNote(
                field=fname,
                approved=approved,
                source=winner.source,
                value=winner.value,
                reason=reason,
            )
        )
        if approved:
            out[fname] = entry
            continue
        remaining = [c for c in entry.candidates if c is not winner]
        out[fname] = _rebuild_entry_after_rejection(fname, remaining)

    return out, tuple(notes)
