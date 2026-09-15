"""
Context-guided strict field extraction via LLM.

Uses :class:`~ocean_read.domain.validation.document_context.DocumentContext` plus
layout-serialized blocks so the model can distinguish parties, totals, and duplicate labels.
"""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.document_context import DocumentContext
from ocean_read.domain.validation.document_layout import block_by_id, build_llm_document_view, serialize_blocks_for_llm
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)


def _normalize_needle(text: str) -> str:
    """Lowercase, collapse whitespace for fuzzy block matching."""

    return " ".join((text or "").lower().split())


def _resolve_anchor_block(
    blocks: list[TextBlock],
    index: dict[str, TextBlock],
    *,
    block_id: str,
    evidence_text: str,
    value: Any,
) -> TextBlock | None:
    """Pick the PDF block that best matches LLM evidence (never default to the first block)."""

    bid = (block_id or "").strip()
    cited = index.get(bid) if bid else None

    needles: list[str] = []
    ev = _normalize_needle(evidence_text)
    if len(ev) >= 4:
        needles.append(ev)
    val = _normalize_needle(str(value))
    if len(val) >= 3 and val not in needles:
        needles.append(val)

    if cited and needles:
        cited_hay = _normalize_needle(cited.text or "")
        if any(needle in cited_hay for needle in needles):
            return cited

    best: TextBlock | None = None
    best_score = 0
    for block in blocks:
        hay = _normalize_needle(block.text or "")
        if not hay:
            continue
        for needle in needles:
            if needle in hay:
                score = len(needle)
                if score > best_score:
                    best_score = score
                    best = block
    if best is not None:
        return best
    return cited


def _field_spec_lines(fields_spec: dict[str, Any], field_names: list[str]) -> str:
    lines: list[str] = []
    for name in field_names:
        spec = fields_spec.get(name)
        if not isinstance(spec, dict):
            continue
        parts = [f"- {name} (type={spec.get('type', 'string')})"]
        aliases = spec.get("aliases") or []
        if aliases:
            parts.append(f"labels: {', '.join(str(a) for a in aliases[:8])}")
        role = spec.get("semantic_role")
        if role:
            parts.append(f"semantic_role={role}")
        hint = spec.get("extraction_hint")
        if hint:
            parts.append(f"hint: {hint}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _coerce_value(raw: Any, spec: dict[str, Any]) -> Any | None:
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


_SYSTEM = """You extract strict schema fields from a PDF using DOCUMENT_CONTEXT and BLOCKS_WITH_LAYOUT.

Rules:
- Use semantic_role and region roles (issuer, recipient, payment_summary, etc.) to pick the correct party/value.
- When the same label appears multiple times (e.g. totals, dates), choose the instance that matches the field's role — not line items or unrelated sections.
- Return one value per requested field. Use null if truly absent.
- evidence_text: short quote from the document. block_id: must be an id from BLOCKS_WITH_LAYOUT.

JSON shape only:
{
  "fields": {
    "field_name": {
      "value": <string|number|null>,
      "block_id": "b12",
      "evidence_text": "short quote"
    }
  }
}"""


async def contextual_extract_fields(
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
    field_names: list[str],
    context: DocumentContext,
    *,
    client: OllamaLLMClient,
    document_text: str | None = None,
) -> list[ExtractionCandidate]:
    """Extract fields with document understanding; attaches evidence from cited ``block_id``."""

    if (not blocks and not (document_text or "").strip()) or not field_names:
        return []
    layout = (document_text or "").strip() or build_llm_document_view(markdown=None, blocks=blocks)
    field_lines = _field_spec_lines(fields_spec, field_names)
    user = (
        f"DOCUMENT_CONTEXT:\n{context.to_prompt_text()}\n\n"
        f"FIELDS_TO_EXTRACT:\n{field_lines}\n\n"
        f"BLOCKS_WITH_LAYOUT:\n{layout}\n"
    )
    try:
        raw = await client.complete(_SYSTEM, user, temperature=0.0)
        data: Any = loads_json_maybe_with_fence(raw)
    except Exception as exc:
        logger.info("Contextual extraction skipped: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    fields_out = data.get("fields")
    if not isinstance(fields_out, dict):
        return []
    index = block_by_id(blocks)
    out: list[ExtractionCandidate] = []
    for name in field_names:
        spec = fields_spec.get(name)
        if not isinstance(spec, dict):
            continue
        entry = fields_out.get(name)
        if not isinstance(entry, dict):
            continue
        val = _coerce_value(entry.get("value"), spec)
        if val is None:
            continue
        bid = str(entry.get("block_id") or "").strip()
        evidence = str(entry.get("evidence_text") or val)[:280]
        anchor = _resolve_anchor_block(
            blocks,
            index,
            block_id=bid,
            evidence_text=evidence,
            value=val,
        )
        out.append(
            ExtractionCandidate(
                field=name,
                value=val,
                source="llm_context",
                confidence=0.88,
                block_id=anchor.id if anchor else bid,
                page=anchor.page if anchor else 1,
                evidence_text=evidence,
                bbox=anchor.bbox if anchor else None,
                section_label=anchor.section_label if anchor else None,
            )
        )
    return out
