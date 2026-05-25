"""Orchestrate PDF → blocks → ensemble extraction → mapping → resolution → schema validation."""

from __future__ import annotations

from typing import Any, Literal, cast

from ocean_read.config import get_settings
from ocean_read.domain.validation.engine import validate_schema
from ocean_read.domain.validation.extractors_wine import ensemble_wine_extractors
from ocean_read.domain.validation.mapping import check_inconsistencies, map_candidates_to_schema
from ocean_read.domain.validation.pdf_blocks import choose_blocks_for_m3_groups, parse_pdf_blocks
from ocean_read.domain.validation.pdf_hash import compute_pdf_hash
from ocean_read.domain.validation.pipeline_result import PipelineValidationResult
from ocean_read.domain.validation.snapshot_serializer import serialize_pipeline_snapshots
from ocean_read.domain.validation.resolution import resolve_from_field_map
from ocean_read.providers.ollama import OllamaLLMClient
from ocean_read.services.validation_llm import llm_fallback_wine_fields


async def _gap_fill_pass(
    candidates: list[Any],
    *,
    blocks: list[Any],
    use_llm: bool,
) -> list[Any]:
    """Stage 4 — extend candidates with LLM hypotheses when enabled (M1: single merge point)."""

    if not use_llm or not blocks:
        return candidates
    llm = OllamaLLMClient()
    try:
        extra = await llm_fallback_wine_fields(blocks, client=llm)
        return [*candidates, *extra]
    finally:
        await llm.aclose()


async def run_wine_pdf_validation(
    pdf_bytes: bytes,
    *,
    schema_body: dict[str, Any],
    schema_key: str,
    version_label: str,
    llm_fallback: bool | None = None,
) -> PipelineValidationResult:
    """Eight-stage pipeline: parse → discover → map → gap-fill → inconsistency → resolve → validate → assemble."""

    use_llm = get_settings().validation_llm_fallback_enabled if llm_fallback is None else llm_fallback

    pdf_hash = compute_pdf_hash(pdf_bytes)

    # Stage 1 — layout parse (evidence / extractors); span blocks for M3 table groups when needed
    blocks = parse_pdf_blocks(pdf_bytes)
    group_blocks = choose_blocks_for_m3_groups(schema_body, pdf_bytes, blocks)
    # Stage 2 — discovery (regex + layout ensemble)
    candidates = ensemble_wine_extractors(blocks)
    # Stages 3–4 — schema mapping after optional gap-fill augmentation
    candidates = await _gap_fill_pass(
        candidates,
        blocks=blocks,
        use_llm=use_llm,
    )
    schema_fields = schema_body.get("fields") or {}
    field_map = map_candidates_to_schema(candidates, schema_fields)
    # Stage 5 — inconsistency / ambiguity
    inc = check_inconsistencies(field_map)
    if inc.has_ambiguity:
        pipeline_snapshots = serialize_pipeline_snapshots(
            blocks=blocks,
            candidates=candidates,
            field_map=field_map,
            inconsistency=inc,
            resolved_document={},
        )
        return PipelineValidationResult(
            status="AMBIGUOUS",
            schema_key=schema_key,
            schema_version=version_label,
            errors=(),
            ambiguous_fields=inc.ambiguous_fields,
            resolved_values=None,
            schema_body_snapshot=schema_body,
            field_rule_outcomes=(),
            pdf_hash=pdf_hash,
            pipeline_snapshots=pipeline_snapshots,
        )
    # Stage 6 — resolution (deterministic tie-break)
    resolved, evidence_map = resolve_from_field_map(field_map)
    # Stages 7–8 — rule engine + status
    rep = validate_schema(
        resolved=resolved,
        schema_body=schema_body,
        schema_key=schema_key,
        version_label=version_label,
        evidence_map=evidence_map,
        blocks=group_blocks,
    )
    pipeline_snapshots = serialize_pipeline_snapshots(
        blocks=blocks,
        candidates=candidates,
        field_map=field_map,
        inconsistency=inc,
        resolved_document=resolved,
    )
    return PipelineValidationResult(
        status=cast(Literal["PASS", "FAIL"], rep.status),
        schema_key=schema_key,
        schema_version=version_label,
        errors=rep.errors,
        ambiguous_fields=(),
        resolved_values=resolved,
        schema_body_snapshot=schema_body,
        field_rule_outcomes=rep.outcomes,
        pdf_hash=pdf_hash,
        pipeline_snapshots=pipeline_snapshots,
    )
