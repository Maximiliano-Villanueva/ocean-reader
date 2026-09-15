"""
LLM pass: infer what a PDF is about and how its blocks relate (roles, regions).

Output is reused by contextual field extraction — not tied to any document type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ocean_read.domain.validation.document_layout import build_llm_document_view, serialize_blocks_for_llm
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.providers.ollama import OllamaLLMClient, loads_json_maybe_with_fence

logger = logging.getLogger(__name__)

_SYSTEM = """You analyze PDF text that was split into numbered blocks with layout hints (page, column, bbox).
The reading order may not match visual layout — use column and bbox to infer structure.

Return JSON only:
{
  "document_type": "short label e.g. invoice, lab_report, form",
  "summary": "1-2 sentences: what this document is and its main purpose",
  "regions": [
    {
      "role": "semantic role e.g. issuer, recipient, line_items, payment_summary, header, footer, body",
      "block_ids": ["b0", "b1"],
      "description": "what this region contains"
    }
  ],
  "disambiguation_notes": [
    "free-text hints e.g. which labels denote amount due vs line subtotals"
  ]
}
Use block ids exactly as given. Regions may overlap; list every distinct role you can infer."""


@dataclass(frozen=True)
class DocumentRegion:
    role: str
    block_ids: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class DocumentContext:
    """Inferred structure of a PDF for downstream extraction."""

    document_type: str
    summary: str
    regions: tuple[DocumentRegion, ...]
    disambiguation_notes: tuple[str, ...] = ()

    def to_prompt_text(self) -> str:
        lines = [
            f"Document type: {self.document_type}",
            f"Summary: {self.summary}",
            "Regions:",
        ]
        for r in self.regions:
            ids = ", ".join(r.block_ids[:12])
            suffix = "…" if len(r.block_ids) > 12 else ""
            lines.append(f"  - {r.role}: {r.description} [blocks: {ids}{suffix}]")
        if self.disambiguation_notes:
            lines.append("Disambiguation:")
            for n in self.disambiguation_notes:
                lines.append(f"  - {n}")
        return "\n".join(lines)


def _parse_context(data: Any) -> DocumentContext | None:
    if not isinstance(data, dict):
        return None
    regions_raw = data.get("regions") or []
    regions: list[DocumentRegion] = []
    if isinstance(regions_raw, list):
        for item in regions_raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "unknown").strip()
            desc = str(item.get("description") or "").strip()
            bids = item.get("block_ids") or []
            if not isinstance(bids, list):
                bids = []
            regions.append(
                DocumentRegion(
                    role=role,
                    block_ids=tuple(str(x) for x in bids if x),
                    description=desc or role,
                )
            )
    notes_raw = data.get("disambiguation_notes") or []
    notes = tuple(str(n) for n in notes_raw if n) if isinstance(notes_raw, list) else ()
    return DocumentContext(
        document_type=str(data.get("document_type") or "document").strip(),
        summary=str(data.get("summary") or "").strip(),
        regions=tuple(regions),
        disambiguation_notes=notes,
    )


async def infer_document_context(
    blocks: list[TextBlock],
    *,
    client: OllamaLLMClient,
    schema_field_summary: str = "",
    document_text: str | None = None,
) -> DocumentContext | None:
    """Run the understanding pass; returns ``None`` on LLM/parse failure."""

    if not blocks and not (document_text or "").strip():
        return None
    layout = (document_text or "").strip() or serialize_blocks_for_llm(blocks)
    user_parts = ["BLOCKS_WITH_LAYOUT:\n", layout]
    if schema_field_summary.strip():
        user_parts.append("\nSCHEMA_FIELDS_TO_EXTRACT_LATER:\n" + schema_field_summary.strip())
    user = "\n".join(user_parts)
    try:
        raw = await client.complete(_SYSTEM, user, temperature=0.0)
        parsed = loads_json_maybe_with_fence(raw)
    except Exception as exc:
        logger.info("Document context inference skipped: %s", exc)
        return None
    ctx = _parse_context(parsed)
    if ctx is None:
        logger.info("Document context parse failed")
    return ctx
