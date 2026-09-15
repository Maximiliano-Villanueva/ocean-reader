"""
LLM gap-fill for arbitrary strict schema fields (dates, invoice ids, etc.).

Used when regex/layout leave required fields missing. Lower priority than deterministic extractors.
"""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)


def _field_descriptions(fields_spec: dict[str, Any], names: list[str]) -> str:
    lines: list[str] = []
    for name in names:
        spec = fields_spec.get(name)
        if not isinstance(spec, dict):
            continue
        typ = spec.get("type", "string")
        aliases = spec.get("aliases") or []
        alias_txt = ", ".join(str(a) for a in aliases[:6])
        lines.append(f"- {name} ({typ}): PDF labels like {alias_txt or name}")
    return "\n".join(lines)


def _coerce_llm_value(raw: Any, spec: dict[str, Any]) -> Any | None:
    if raw is None:
        return None
    typ = spec.get("type")
    if typ == "number":
        try:
            return float(str(raw).replace(",", ""))
        except (TypeError, ValueError):
            return None
    if typ == "date":
        text = str(raw).strip()
        return text[:120] if text else None
    text = str(raw).strip()
    return text[:500] if text else None


async def llm_fallback_schema_fields(
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
    field_names: list[str],
    *,
    client: OllamaLLMClient,
    document_text: str | None = None,
) -> list[ExtractionCandidate]:
    """Extract missing strict fields from document text (Spanish/English dates, labeled values)."""

    if not field_names:
        return []
    text = (document_text or "").strip() or "\n".join(b.text for b in blocks[:100])[:14000]
    if not text:
        return []
    desc = _field_descriptions(fields_spec, field_names)
    keys_json = ", ".join(f'"{n}": ...' for n in field_names)
    system = (
        "You extract structured fields from invoice/lab PDF text. "
        f"Return JSON only: {{{keys_json}}}. "
        "Use null for unknown fields. "
        "Dates: preserve the exact phrase from the document (e.g. '9 de agosto de 2025' or '9 August 2025'). "
        "Numbers: numeric values only. Strings: concise values without extra labels. No prose."
    )
    user = f"Fields to extract:\n{desc}\n\nDocument text:\n{text}\n"
    try:
        raw = await client.complete(system, user, temperature=0.0)
        data: Any = loads_json_maybe_with_fence(raw)
    except Exception as exc:
        logger.info("Schema LLM fallback skipped: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    anchor = blocks[0]
    out: list[ExtractionCandidate] = []
    for name in field_names:
        spec = fields_spec.get(name)
        if not isinstance(spec, dict):
            continue
        val = _coerce_llm_value(data.get(name), spec)
        if val is None:
            continue
        out.append(
            ExtractionCandidate(
                field=name,
                value=val,
                source="llm",
                confidence=0.45,
                block_id=anchor.id,
                page=anchor.page,
                evidence_text=str(val)[:280],
                bbox=anchor.bbox,
                section_label=anchor.section_label,
            )
        )
    return out


def missing_fields_for_llm(
    field_map: dict[str, Any],
    fields_spec: dict[str, Any],
    *,
    global_llm_enabled: bool,
) -> list[str]:
    """Field names that should receive an LLM gap-fill attempt."""

    names: list[str] = []
    for fname, spec in (fields_spec or {}).items():
        if not isinstance(spec, dict):
            continue
        entry = field_map.get(fname)
        status = getattr(entry, "status", None) or (entry or {}).get("status")
        if status != "missing":
            continue
        per_field = spec.get("llm_fallback") is True
        is_date = spec.get("type") == "date"
        if global_llm_enabled or per_field or is_date:
            names.append(str(fname))
    return names
