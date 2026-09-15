"""
Orchestrate document understanding + contextual extraction for the validation pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from ocean_read.domain.validation.contextual_extraction import contextual_extract_fields
from ocean_read.domain.validation.document_context import infer_document_context
from ocean_read.domain.validation.extraction_planning import fields_needing_contextual_extraction
from ocean_read.domain.validation.mapping import FieldEntry, map_candidates_to_schema
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate
from ocean_read.providers.ollama import OllamaLLMClient

logger = logging.getLogger(__name__)


def _schema_field_summary(fields_spec: dict[str, Any]) -> str:
    lines: list[str] = []
    for fname, spec in (fields_spec or {}).items():
        if not isinstance(spec, dict):
            continue
        role = spec.get("semantic_role") or ""
        aliases = ", ".join(str(a) for a in (spec.get("aliases") or [])[:4])
        lines.append(f"- {fname} ({spec.get('type', 'string')}){f' role={role}' if role else ''} {aliases}")
    return "\n".join(lines)


async def run_contextual_extraction_pass(
    candidates: list[ExtractionCandidate],
    field_map: dict[str, FieldEntry],
    *,
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
    schema_body: dict[str, Any],
    client: OllamaLLMClient,
    document_text: str | None = None,
) -> tuple[list[ExtractionCandidate], dict[str, FieldEntry]]:
    """
    When needed, infer document context then extract target fields with layout awareness.
    """

    names = fields_needing_contextual_extraction(
        field_map, fields_spec, candidates, schema_body
    )
    if not names:
        return candidates, field_map

    context = await infer_document_context(
        blocks,
        client=client,
        schema_field_summary=_schema_field_summary(fields_spec),
        document_text=document_text,
    )
    if context is None:
        logger.info("Contextual pass: no document context; skipping field extraction")
        return candidates, field_map

    extra = await contextual_extract_fields(
        blocks,
        fields_spec,
        names,
        context,
        client=client,
        document_text=document_text,
    )
    if not extra:
        return candidates, field_map
    merged = [*candidates, *extra]
    return merged, map_candidates_to_schema(merged, fields_spec)
