"""M3 repeating groups: extract list-style rows from a section and validate row expressions."""

from __future__ import annotations

import re
from typing import Any

from ocean_read.domain.validation.outcomes import FieldRuleOutcome, FieldValidationError
from ocean_read.domain.validation.expression_evaluator import (
    ExpressionEvaluationError,
    evaluate_boolean_expression,
    expression_identifiers,
    interpolate_field_template,
)
from ocean_read.domain.validation.pdf_blocks import TextBlock


def _slug_label(s: str) -> str:
    """Normalize a human or snake_case label for comparison (``Lower bound`` → ``lower_bound``)."""

    s2 = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip().lower())
    return re.sub(r"_+", "_", s2).strip("_")


def _canonical_row_field(line_key: str, field_order: list[str]) -> str | None:
    """Map a line's left-hand label to a ``row_fields`` name, or ``None``."""

    ls = _slug_label(line_key)
    for fname in field_order:
        if ls == _slug_label(fname):
            return fname
    return None


def _parse_sections_paragraph(
    para: str,
    field_order: list[str],
    row_fields: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse one blank-line-separated paragraph into a typed row dict."""

    collected: dict[str, str] = {}
    for line in para.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key_part, val_part = line.split(":", 1)
        else:
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            key_part, val_part = parts[0], parts[1]
        fname = _canonical_row_field(key_part, field_order)
        if fname is None:
            continue
        collected[fname] = val_part.strip()
    if len(collected) != len(field_order):
        return None
    tokens = [collected[f] for f in field_order]
    if _looks_like_header_row(tokens, field_order):
        return None
    return _build_row_from_tokens(tokens, field_order, row_fields)


def _extract_sections_structure_rows(
    blocks: list[TextBlock],
    hint: str,
    field_order: list[str],
    row_fields: dict[str, Any],
) -> list[dict[str, Any]]:
    """One row per blank-line-separated paragraph; lines are ``Label: value`` (or two tokens)."""

    blob = _section_text_blob(blocks, hint)
    if not blob.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", blob) if p.strip()]
    rows_out: list[dict[str, Any]] = []
    for para in paragraphs:
        built = _parse_sections_paragraph(para, field_order, row_fields)
        if built:
            rows_out.append(built)
    return rows_out


def _block_matches_section(hint: str, b: TextBlock) -> bool:
    h = hint.strip().lower()
    if not h:
        return False
    label = (b.section_label or "").lower()
    first = b.text.strip().splitlines()[0].lower() if b.text.strip() else ""
    return h in label or h in first or h in b.text.lower()


def _blocks_for_section(blocks: list[TextBlock], hint: str) -> list[TextBlock]:
    """Layout blocks under a section header (PyMuPDF often emits one block per line).

    After a block whose first line equals ``section_hint``, following blocks on later
    baselines are included until the document ends. Falls back to :func:`_block_matches_section`
    when no header line is found (single blob block or ``section_label`` on the block).
    """

    h = hint.strip().lower()
    if not h:
        return []
    ordered = sorted(blocks, key=lambda b: (b.page, b.bbox[1], b.bbox[0]))
    body: list[TextBlock] = []
    in_section = False
    for b in ordered:
        first = b.text.strip().splitlines()[0].strip().lower() if b.text.strip() else ""
        if first == h or (h in first and len(first) <= len(h) + 6):
            in_section = True
            continue
        if in_section:
            body.append(b)
    if body:
        return body
    return [b for b in blocks if _block_matches_section(hint, b)]


def _section_text_blob(blocks: list[TextBlock], hint: str) -> str:
    """Concatenate header + body blocks for a ``section_hint`` (layout PDFs and single-block blobs)."""

    h = hint.strip().lower()
    if not h:
        return ""
    ordered = sorted(blocks, key=lambda b: (b.page, b.bbox[1], b.bbox[0]))
    parts: list[str] = []
    in_section = False
    for b in ordered:
        first = b.text.strip().splitlines()[0].strip().lower() if b.text.strip() else ""
        if first == h or (h in first and len(first) <= len(h) + 6):
            in_section = True
            parts.append(b.text)
            continue
        if in_section:
            parts.append(b.text)
    if parts:
        return "\n".join(parts)
    return "\n".join(b.text for b in blocks if _block_matches_section(hint, b))


def _build_row_from_tokens(
    tokens: list[str],
    field_order: list[str],
    row_fields: dict[str, Any],
) -> dict[str, Any] | None:
    """Map ``tokens`` to typed row dict, or ``None`` if width/header/coercion fails."""

    if len(tokens) != len(field_order):
        return None
    if _looks_like_header_row(tokens, field_order):
        return None
    row: dict[str, Any] = {}
    for i, fname in enumerate(field_order):
        spec = row_fields[fname] if isinstance(row_fields[fname], dict) else {}
        typ = spec.get("type")
        tok = tokens[i]
        if typ == "string":
            row[fname] = tok
        elif typ == "number":
            try:
                row[fname] = float(tok)
            except ValueError:
                return None
        else:
            try:
                row[fname] = float(tok)
            except ValueError:
                row[fname] = tok
    return row


def _cluster_blocks_into_rows(blocks: list[TextBlock], row_y_tol: float) -> list[list[TextBlock]]:
    """Group spans/blocks that share a text baseline (top ``y`` within tolerance)."""

    if not blocks:
        return []
    blocks_sorted = sorted(blocks, key=lambda b: (b.page, b.bbox[1], b.bbox[0]))
    rows_out: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    anchor_y: float | None = None
    for b in blocks_sorted:
        y = float(b.bbox[1])
        if not current:
            current.append(b)
            anchor_y = y
        elif anchor_y is not None and abs(y - anchor_y) <= row_y_tol:
            current.append(b)
        else:
            rows_out.append(current)
            current = [b]
            anchor_y = y
    if current:
        rows_out.append(current)
    return rows_out


def _cells_from_row_spans(row_blocks: list[TextBlock], gap: float) -> list[str]:
    """Merge adjacent spans into cells when horizontal gap exceeds ``gap`` (PDF points)."""

    sorted_row = sorted(row_blocks, key=lambda b: (b.bbox[0], b.bbox[1]))
    cells: list[str] = []
    parts: list[str] = []
    current_right: float | None = None
    for b in sorted_row:
        left, _top, right, _bottom = (float(b.bbox[0]), float(b.bbox[1]), float(b.bbox[2]), float(b.bbox[3]))
        t = b.text.strip()
        if not t:
            continue
        if current_right is None:
            parts.append(t)
            current_right = right
        elif left - current_right > gap:
            cells.append(" ".join(parts).strip())
            parts = [t]
            current_right = right
        else:
            parts.append(t)
            current_right = max(current_right, right)
    if parts:
        cells.append(" ".join(parts).strip())
    return cells


def extract_table_rows_bbox_only(
    blocks: list[TextBlock],
    _group_name: str,
    group_spec: dict[str, Any],
    *,
    column_gap_pt: float | None = None,
    row_y_tolerance_pt: float | None = None,
) -> list[dict[str, Any]]:
    """Extract table rows using horizontal gaps and row clustering (span-level blocks).

    Optional ``group_spec`` keys: ``column_gap_pt`` (default 12), ``row_y_tolerance_pt`` (default 4).
    Intended for tests and for ``extract_group_rows`` when ``structure_hint`` is ``table``.
    """

    hint = str(group_spec.get("section_hint") or "").strip().lower()
    row_fields = group_spec.get("row_fields") or {}
    if not hint or not isinstance(row_fields, dict) or not row_fields:
        return []
    field_order = list(row_fields.keys())
    try:
        gap = float(column_gap_pt) if column_gap_pt is not None else float(group_spec.get("column_gap_pt") or 12.0)
    except (TypeError, ValueError):
        gap = 12.0
    try:
        row_y_tol = (
            float(row_y_tolerance_pt) if row_y_tolerance_pt is not None else float(group_spec.get("row_y_tolerance_pt") or 4.0)
        )
    except (TypeError, ValueError):
        row_y_tol = 4.0

    section_blocks = _blocks_for_section(blocks, hint)
    if not section_blocks:
        return []

    rows_out: list[dict[str, Any]] = []
    for row_blocks in _cluster_blocks_into_rows(section_blocks, row_y_tol):
        tokens = _cells_from_row_spans(row_blocks, gap)
        built = _build_row_from_tokens(tokens, field_order, row_fields)
        if built:
            rows_out.append(built)
    return rows_out


def extract_group_rows(blocks: list[TextBlock], _group_name: str, group_spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract rows for a repeating ``groups`` entry.

    ``structure_hint``:

    - ``sections``: blank-line-separated **mini-sections**; each paragraph uses ``Label: value`` lines
      (or ``label value``) whose labels match ``row_fields`` keys (slug-normalized).
    - ``table`` (default): tries **bbox column clustering** on span-level blocks first; then
      **pipe-separated** cells when ``|`` is present; otherwise whitespace-separated tokens per line.
    - ``list``: whitespace-separated tokens per line (layout blocks; no bbox table path).

    A header line whose cells match ``row_fields`` keys (case-insensitive) is skipped.
    """

    hint = str(group_spec.get("section_hint") or "").strip().lower()
    if not hint:
        return []
    row_fields = group_spec.get("row_fields") or {}
    if not isinstance(row_fields, dict) or not row_fields:
        return []

    field_order = list(row_fields.keys())
    structure = str(group_spec.get("structure_hint") or "table").lower()
    if structure == "sections":
        return _extract_sections_structure_rows(blocks, hint, field_order, row_fields)
    if structure == "table":
        bbox_rows = extract_table_rows_bbox_only(blocks, _group_name, group_spec)
        if bbox_rows:
            return bbox_rows
    blob = _section_text_blob(blocks, hint)
    rows_out: list[dict[str, Any]] = []
    for raw_line in blob.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = _split_row_tokens(line, field_order, structure)
        if tokens is None:
            continue
        built = _build_row_from_tokens(tokens, field_order, row_fields)
        if built:
            rows_out.append(built)
    return rows_out


def _split_row_tokens(line: str, field_order: list[str], structure: str) -> list[str] | None:
    n = len(field_order)
    st = (structure or "table").lower()
    if st == "table" and "|" in line:
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p != ""]
        if len(parts) == n:
            return parts
    parts = line.split()
    if len(parts) == n:
        return parts
    return None


def _looks_like_header_row(tokens: list[str], field_order: list[str]) -> bool:
    if len(tokens) != len(field_order):
        return False
    return all(t.replace(" ", "_").lower() == f.replace(" ", "_").lower() for t, f in zip(tokens, field_order))


def validate_repeating_groups(
    blocks: list[TextBlock],
    schema_body: dict[str, Any],
    evidence_map: dict[str, dict[str, Any]] | None,
) -> tuple[list[FieldValidationError], list[FieldRuleOutcome]]:
    """Validate ``groups`` in ``schema_body`` using extracted rows. Empty extraction → FAIL."""

    groups = schema_body.get("groups") or {}
    if not isinstance(groups, dict) or not groups:
        return [], []
    ev = evidence_map or {}
    errors: list[FieldValidationError] = []
    outcomes: list[FieldRuleOutcome] = []

    for group_name, group_spec in groups.items():
        if not isinstance(group_spec, dict):
            continue
        rows = extract_group_rows(blocks, str(group_name), group_spec)
        if not rows:
            errors.append(
                FieldValidationError(
                    field=str(group_name),
                    value=None,
                    expected="at least one row in section",
                    rule="group_not_found",
                    evidence={"section_hint": group_spec.get("section_hint")},
                )
            )
            outcomes.append(
                FieldRuleOutcome(
                    field=str(group_name),
                    rule="group_not_found",
                    passed=False,
                    value=None,
                    expected="rows",
                    evidence=None,
                )
            )
            continue

        row_rules = group_spec.get("row_rules") or []
        if not isinstance(row_rules, list):
            continue

        for row_idx, row in enumerate(rows):
            row_evidence = _row_evidence_stub(row_idx, group_name, ev)
            for rr in row_rules:
                if not isinstance(rr, dict):
                    continue
                rid = str(rr.get("id") or "row_rule")
                expr = str(rr.get("expression") or "")
                msg_t = str(rr.get("error_message") or f"Row rule {rid} failed")
                if not expr:
                    continue
                num_binding: dict[str, float] = {}
                skip = False
                for name, val in row.items():
                    if isinstance(val, bool):
                        skip = True
                        break
                    if isinstance(val, (int, float)):
                        num_binding[str(name)] = float(val)
                if skip:
                    continue
                try:
                    idents = expression_identifiers(expr)
                except ExpressionEvaluationError:
                    errors.append(
                        FieldValidationError(
                            field=f"{group_name}[{row_idx}]",
                            value=row,
                            expected="valid expression",
                            rule=rid,
                            evidence=row_evidence,
                        )
                    )
                    outcomes.append(
                        FieldRuleOutcome(
                            field=f"{group_name}[{row_idx}]",
                            rule=rid,
                            passed=False,
                            value=row,
                            expected=expr,
                            evidence=row_evidence,
                        )
                    )
                    continue
                if any(k not in num_binding for k in idents):
                    continue
                try:
                    passed = evaluate_boolean_expression(expr, num_binding)
                except ExpressionEvaluationError:
                    passed = False
                interp = interpolate_field_template(msg_t, {**{k: str(v) for k, v in row.items()}})
                if passed:
                    outcomes.append(
                        FieldRuleOutcome(
                            field=f"{group_name}[{row_idx}]",
                            rule=rid,
                            passed=True,
                            value=row,
                            expected=expr,
                            evidence=row_evidence,
                        )
                    )
                else:
                    errors.append(
                        FieldValidationError(
                            field=f"{group_name}[{row_idx}]",
                            value=row,
                            expected=expr,
                            rule=rid,
                            evidence=row_evidence,
                        )
                    )
                    outcomes.append(
                        FieldRuleOutcome(
                            field=f"{group_name}[{row_idx}]",
                            rule=rid,
                            passed=False,
                            value=row,
                            expected=interp,
                            evidence=row_evidence,
                        )
                    )
    return errors, outcomes


def _row_evidence_stub(row_idx: int, group_name: str, ev: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"group": group_name, "row_index": row_idx, "by_field": {k: v for k, v in ev.items()}}
