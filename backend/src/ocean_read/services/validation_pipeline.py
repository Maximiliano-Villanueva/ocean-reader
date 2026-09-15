"""Orchestrate PDF → blocks → ensemble extraction → mapping → resolution → schema validation."""

from __future__ import annotations

import logging
from typing import Any, Literal, cast

from ocean_read.config import get_settings
from ocean_read.domain.validation.ambiguity_policy import apply_ambiguity_policies
from ocean_read.domain.validation.candidate_cleanup import dedupe_extraction_candidates, reconcile_field_map
from ocean_read.domain.validation.extraction_judge import apply_extraction_judge, judge_enabled_for_schema
from ocean_read.domain.validation.engine import validate_schema
from ocean_read.domain.validation.extractors_schema import ensemble_schema_extractors
from ocean_read.domain.validation.extractors_wine import ensemble_wine_extractors
from ocean_read.domain.validation.evidence_bbox import (
    refine_extraction_candidate_bboxes,
    refine_field_map_bboxes,
)
from ocean_read.domain.validation.mapping import check_inconsistencies, map_candidates_to_schema
from ocean_read.domain.validation.docling_images import analyze_docling_pictures
from ocean_read.domain.validation.docling_parse import parse_pdf_with_docling
from ocean_read.domain.validation.document_layout import build_llm_document_view
from ocean_read.domain.validation.extraction_planning import schema_extraction_config
from ocean_read.domain.validation.pdf_blocks import choose_blocks_for_m3_groups, parse_pdf_blocks
from ocean_read.domain.validation.pdf_hash import compute_pdf_hash
from ocean_read.domain.validation.pipeline_result import PipelineValidationResult
from ocean_read.domain.validation.snapshot_serializer import serialize_pipeline_snapshots
from ocean_read.domain.validation.resolution import resolve_from_field_map
from ocean_read.domain.validation.open_ended_runner import merge_open_ended_into_status, run_open_ended_fields
from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.schema_normalizer import normalize_schema_body, schema_has_open_ended
from ocean_read.providers.ollama import OllamaLLMClient
from ocean_read.domain.validation.pdf_page_images import pdf_text_is_sparse
from ocean_read.services.validation_llm import llm_fallback_wine_fields
from ocean_read.services.validation_contextual import run_contextual_extraction_pass
from ocean_read.services.validation_llm_schema import (
    llm_fallback_schema_fields,
    missing_fields_for_llm,
)
from ocean_read.services.validation_llm_vision import (
    extraction_failure_on_fail,
    missing_required_field_names,
    vision_fallback_candidates,
)

logger = logging.getLogger(__name__)


async def _gap_fill_pass(
    candidates: list[Any],
    *,
    blocks: list[Any],
    use_llm: bool,
    schema_fields: dict[str, Any],
) -> list[Any]:
    """Stage 4 — extend candidates with LLM hypotheses when enabled (M1: single merge point)."""

    if not blocks:
        return candidates
    llm = OllamaLLMClient()
    try:
        extra: list[Any] = []
        wine_keys = {"ph", "alcohol", "quality"}
        if use_llm and (not schema_fields or wine_keys.intersection(schema_fields)):
            extra.extend(await llm_fallback_wine_fields(blocks, client=llm))
        return [*candidates, *extra]
    finally:
        await llm.aclose()


async def _schema_llm_pass(
    candidates: list[Any],
    field_map: dict[str, Any],
    *,
    blocks: list[TextBlock],
    schema_fields: dict[str, Any],
    schema_body: dict[str, Any],
    use_llm: bool,
    use_document_understanding: bool,
    document_text: str | None = None,
) -> tuple[list[Any], dict[str, Any], bool]:
    """
    LLM extraction for strict fields.

    When document understanding is enabled, runs context inference + layout-aware extraction.
    Otherwise falls back to flat-text gap-fill for missing fields only.
    """

    if not blocks or not schema_fields:
        return candidates, field_map, False
    llm = OllamaLLMClient()
    context_used = False
    try:
        if use_document_understanding:
            merged, new_map = await run_contextual_extraction_pass(
                candidates,
                field_map,
                blocks=blocks,
                fields_spec=schema_fields,
                schema_body=schema_body,
                client=llm,
                document_text=document_text,
            )
            if merged is not candidates or new_map is not field_map:
                context_used = True
            return merged, new_map, context_used
        names = missing_fields_for_llm(field_map, schema_fields, global_llm_enabled=use_llm)
        if not names:
            return candidates, field_map, False
        extra = await llm_fallback_schema_fields(
            blocks, schema_fields, names, client=llm, document_text=document_text
        )
        if not extra:
            return candidates, field_map, False
        merged = [*candidates, *extra]
        return merged, map_candidates_to_schema(merged, schema_fields), False
    finally:
        await llm.aclose()


async def _vision_gap_fill_pass(
    pdf_bytes: bytes,
    candidates: list[Any],
    field_map: dict[str, Any],
    schema_fields: dict[str, Any],
    blocks: list[TextBlock],
    *,
    use_vision: bool,
) -> tuple[list[Any], dict[str, Any], bool]:
    """Stage 4b — multimodal page images when text is sparse or required fields are missing."""

    if not use_vision or not schema_fields:
        return candidates, field_map, False
    sparse = pdf_text_is_sparse(blocks, pdf_bytes)
    missing = missing_required_field_names(field_map, schema_fields)
    if not sparse and not missing:
        return candidates, field_map, False
    extra = await vision_fallback_candidates(pdf_bytes, schema_fields)
    if not extra:
        return candidates, field_map, False
    merged = [*candidates, *extra]
    new_map = map_candidates_to_schema(merged, schema_fields)
    return merged, new_map, True


def _extraction_meta(
    vision_used: bool,
    context_pass_used: bool,
    judge_notes: tuple[Any, ...],
    *,
    parser: str = "docling",
    read_images: bool = False,
    markdown_chars: int = 0,
) -> dict[str, Any]:
    """Pipeline diagnostics surfaced on API responses."""

    meta: dict[str, Any] = {
        "vision_fallback_used": vision_used,
        "document_understanding_used": context_pass_used,
        "parser": parser,
        "read_images": read_images,
        "markdown_chars": markdown_chars,
    }
    if judge_notes:
        meta["extraction_judge"] = [
            {
                "field": n.field,
                "approved": n.approved,
                "source": n.source,
                "value": n.value,
                "reason": n.reason,
            }
            for n in judge_notes
        ]
    return meta


async def _open_ended_pass(
    *,
    schema_body: dict[str, Any],
    blocks: list[TextBlock],
    resolved: dict[str, Any],
    enabled: bool,
    document_text: str | None = None,
) -> tuple[Any, ...]:
    if not enabled:
        return ()
    client = OllamaLLMClient()
    try:
        return await run_open_ended_fields(
            schema_body=schema_body,
            blocks=blocks,
            resolved_strict=resolved,
            client=client,
            enabled=True,
            document_text=document_text,
        )
    except Exception:
        return ()
    finally:
        await client.aclose()


async def run_wine_pdf_validation(
    pdf_bytes: bytes,
    *,
    schema_body: dict[str, Any],
    schema_key: str,
    version_label: str,
    llm_fallback: bool | None = None,
    open_ended_enabled: bool | None = None,
    llm_vision: bool | None = None,
) -> PipelineValidationResult:
    """Eight-stage pipeline: parse → discover → map → gap-fill → inconsistency → resolve → validate → assemble."""

    settings = get_settings()
    schema_body = normalize_schema_body(schema_body)
    use_llm = settings.validation_llm_fallback_enabled if llm_fallback is None else llm_fallback
    if open_ended_enabled is None:
        use_open_ended = schema_has_open_ended(schema_body) or settings.validation_open_ended_enabled
    else:
        use_open_ended = bool(open_ended_enabled)
    use_vision = (
        settings.validation_llm_vision_enabled if llm_vision is None else llm_vision
    )
    # Contextual extraction (document understanding + layout-aware LLM) is always on.
    use_understanding = settings.validation_document_understanding_enabled

    pdf_hash = compute_pdf_hash(pdf_bytes)
    vision_used = False
    context_pass_used = False
    judge_notes: tuple[Any, ...] = ()

    # Stage 1 — Docling parse: markdown for LLM, JSON-derived blocks for highlight boxes
    ext_cfg = schema_extraction_config(schema_body)
    read_images = bool(ext_cfg.get("read_images"))
    document_text: str | None = None
    parser_name = "pymupdf"
    try:
        docling_result = parse_pdf_with_docling(pdf_bytes, read_images=read_images)
        parser_name = "docling"
        blocks = docling_result.blocks
        image_markdown = ""
        if read_images and docling_result.pictures:
            pic_client = OllamaLLMClient()
            try:
                image_markdown = await analyze_docling_pictures(docling_result.pictures, client=pic_client)
            finally:
                await pic_client.aclose()
        document_text = build_llm_document_view(
            markdown=docling_result.markdown,
            blocks=blocks,
            image_markdown=image_markdown or None,
        )
    except Exception:
        logger.exception("Docling parse failed; falling back to PyMuPDF blocks")
        blocks = parse_pdf_blocks(pdf_bytes)
        document_text = None
        parser_name = "pymupdf"
        read_images = False

    group_blocks = choose_blocks_for_m3_groups(schema_body, pdf_bytes, blocks)
    # Stage 2 — discovery (wine ensemble + schema regex_hint)
    schema_fields = schema_body.get("fields") or {}
    schema_fields_dict_early = schema_fields if isinstance(schema_fields, dict) else {}
    candidates = [
        *ensemble_schema_extractors(blocks, schema_fields_dict_early),
        *ensemble_wine_extractors(blocks),
    ]
    # Stages 3–4 — schema mapping after optional gap-fill augmentation
    candidates = await _gap_fill_pass(
        candidates,
        blocks=blocks,
        use_llm=use_llm,
        schema_fields=schema_fields_dict_early,
    )
    schema_fields_dict = schema_fields if isinstance(schema_fields, dict) else {}
    field_map = map_candidates_to_schema(candidates, schema_fields_dict)
    candidates, field_map, vision_used = await _vision_gap_fill_pass(
        pdf_bytes,
        candidates,
        field_map,
        schema_fields_dict,
        blocks,
        use_vision=use_vision,
    )
    candidates = dedupe_extraction_candidates(candidates)
    field_map = reconcile_field_map(
        map_candidates_to_schema(candidates, schema_fields_dict),
        schema_fields_dict,
    )
    candidates, field_map, ctx_used = await _schema_llm_pass(
        candidates,
        field_map,
        blocks=blocks,
        schema_fields=schema_fields_dict,
        schema_body=schema_body,
        use_llm=use_llm,
        use_document_understanding=use_understanding,
        document_text=document_text,
    )
    context_pass_used = context_pass_used or ctx_used
    candidates = dedupe_extraction_candidates(candidates)
    field_map = reconcile_field_map(
        map_candidates_to_schema(candidates, schema_fields_dict),
        schema_fields_dict,
    )
    field_map = apply_ambiguity_policies(field_map, schema_fields_dict)
    use_judge = judge_enabled_for_schema(
        schema_body, settings_enabled=settings.validation_extraction_judge_enabled
    )
    if use_judge:
        judge_llm = OllamaLLMClient()
        try:
            field_map, judge_notes = await apply_extraction_judge(
                field_map,
                schema_fields_dict,
                schema_body,
                blocks,
                client=judge_llm,
                enabled=True,
            )
        finally:
            await judge_llm.aclose()
    candidates = refine_extraction_candidate_bboxes(pdf_bytes, candidates)
    field_map = refine_field_map_bboxes(pdf_bytes, field_map)
    # Stage 5 — inconsistency / ambiguity
    inc = check_inconsistencies(field_map)
    if inc.has_ambiguity:
        pipeline_snapshots = serialize_pipeline_snapshots(
            blocks=blocks,
            candidates=candidates,
            field_map=field_map,
            inconsistency=inc,
            resolved_document={},
            extraction_meta=_extraction_meta(
                vision_used,
                context_pass_used,
                judge_notes,
                parser=parser_name,
                read_images=read_images,
                markdown_chars=len(document_text or ""),
            ),
        )
        oe_results = ()
        if use_open_ended:
            oe_results = await _open_ended_pass(
                schema_body=schema_body,
                blocks=blocks,
                resolved={},
                enabled=use_open_ended,
                document_text=document_text,
            )
        status = merge_open_ended_into_status("AMBIGUOUS", oe_results)
        return PipelineValidationResult(
            status=status,
            schema_key=schema_key,
            schema_version=version_label,
            errors=(),
            ambiguous_fields=inc.ambiguous_fields,
            resolved_values=None,
            schema_body_snapshot=schema_body,
            field_rule_outcomes=(),
            pdf_hash=pdf_hash,
            pipeline_snapshots=pipeline_snapshots,
            open_ended_results=oe_results,
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
    if (
        rep.status == "FAIL"
        and use_vision
        and not vision_used
        and extraction_failure_on_fail(rep.errors, field_map, schema_fields_dict)
    ):
        candidates, field_map, vision_used = await _vision_gap_fill_pass(
            pdf_bytes,
            candidates,
            field_map,
            schema_fields_dict,
            blocks,
            use_vision=True,
        )
        candidates, field_map, ctx_used = await _schema_llm_pass(
            candidates,
            field_map,
            blocks=blocks,
            schema_fields=schema_fields_dict,
            schema_body=schema_body,
            use_llm=use_llm,
            use_document_understanding=use_understanding,
        )
        context_pass_used = context_pass_used or ctx_used
        candidates = dedupe_extraction_candidates(candidates)
        field_map = map_candidates_to_schema(candidates, schema_fields_dict)
        field_map = reconcile_field_map(field_map, schema_fields_dict)
        field_map = apply_ambiguity_policies(field_map, schema_fields_dict)
        if use_judge:
            judge_llm = OllamaLLMClient()
            try:
                field_map, judge_notes = await apply_extraction_judge(
                    field_map,
                    schema_fields_dict,
                    schema_body,
                    blocks,
                    client=judge_llm,
                    enabled=True,
                )
            finally:
                await judge_llm.aclose()
        inc = check_inconsistencies(field_map)
        if inc.has_ambiguity:
            pipeline_snapshots = serialize_pipeline_snapshots(
                blocks=blocks,
                candidates=candidates,
                field_map=field_map,
                inconsistency=inc,
                resolved_document={},
                extraction_meta=_extraction_meta(
                    vision_used,
                    context_pass_used,
                    judge_notes,
                    parser=parser_name,
                    read_images=read_images,
                    markdown_chars=len(document_text or ""),
                ),
            )
            oe_results = ()
            if use_open_ended:
                oe_results = await _open_ended_pass(
                    schema_body=schema_body,
                    blocks=blocks,
                    resolved={},
                    enabled=use_open_ended,
                    document_text=document_text,
                )
            status = merge_open_ended_into_status("AMBIGUOUS", oe_results)
            return PipelineValidationResult(
                status=status,
                schema_key=schema_key,
                schema_version=version_label,
                errors=(),
                ambiguous_fields=inc.ambiguous_fields,
                resolved_values=None,
                schema_body_snapshot=schema_body,
                field_rule_outcomes=(),
                pdf_hash=pdf_hash,
                pipeline_snapshots=pipeline_snapshots,
                open_ended_results=oe_results,
            )
        resolved, evidence_map = resolve_from_field_map(field_map)
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
        extraction_meta=_extraction_meta(
            vision_used,
            context_pass_used,
            judge_notes,
            parser=parser_name,
            read_images=read_images,
            markdown_chars=len(document_text or ""),
        ),
    )
    oe_results = ()
    if use_open_ended:
        oe_results = await _open_ended_pass(
            schema_body=schema_body,
            blocks=blocks,
            resolved=resolved,
            enabled=use_open_ended,
            document_text=document_text,
        )
    status = merge_open_ended_into_status(cast(Literal["PASS", "FAIL"], rep.status), oe_results)
    return PipelineValidationResult(
        status=status,
        schema_key=schema_key,
        schema_version=version_label,
        errors=rep.errors,
        ambiguous_fields=(),
        resolved_values=resolved,
        schema_body_snapshot=schema_body,
        field_rule_outcomes=rep.outcomes,
        pdf_hash=pdf_hash,
        pipeline_snapshots=pipeline_snapshots,
        open_ended_results=oe_results,
    )
