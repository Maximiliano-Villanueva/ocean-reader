"""
Schema-driven extraction: ``regex_hint``, label/alias layout heuristics, and common patterns.
"""

from __future__ import annotations

import re
from typing import Any

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+", re.IGNORECASE)
_FLOAT_RE = re.compile(r"[\d.]+")
_USD_RE = re.compile(r"(?i)USD\s*([\d,]+\.?\d*)")
# Spanish prose dates: ``9 de agosto de 2025``
_SPANISH_DATE_RE = re.compile(
    r"(?i)(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})"
)

# Default label phrases when the schema omits ``aliases`` (invoice-style docs).
_BUILTIN_LABELS: dict[str, list[str]] = {
    "invoice_number": ["número de factura", "numero de factura", "invoice number", "invoice no"],
    "invoice_issue_date": ["fecha de emisión", "fecha de emision", "issue date"],
    "invoice_due_date": ["fecha de vencimiento", "due date", "vencimiento"],
    "total_due": ["importe por pagar", "total due", "total", "amount due"],
    "recipient_email": ["email", "correo"],
    "recipient_name": ["facturar a", "bill to", "recipient"],
}


def _safe_float(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _labels_for_field(field: str, spec: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    aliases = list(spec.get("aliases") or [])
    extras = _BUILTIN_LABELS.get(field, []) if not aliases else []
    for raw in [field.replace("_", " "), *aliases, *extras]:
        label = str(raw).strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            out.append(label)
    return out


def _coerce_value(raw: str, spec: dict[str, Any]) -> str | float | None:
    text = raw.strip()
    if not text:
        return None
    typ = spec.get("type")
    if typ == "number":
        m = _USD_RE.search(text) or _FLOAT_RE.search(text.replace(",", ""))
        if not m:
            return None
        chunk = m.group(1) if m.lastindex else m.group(0)
        return _safe_float(chunk)
    if typ == "date":
        return text[:120]
    return text[:500]


def _spanish_date_candidates(
    field: str,
    spec: dict[str, Any],
    blocks: list[TextBlock],
) -> list[ExtractionCandidate]:
    """Supplement ``regex_hint`` for ``type: date`` when labels use Spanish month names."""

    if spec.get("type") != "date":
        return []
    out: list[ExtractionCandidate] = []
    labels = _labels_for_field(field, spec)
    for b in blocks:
        text = b.text or ""
        for m in _SPANISH_DATE_RE.finditer(text):
            snippet = m.group(0).strip()
            if labels:
                lower = text.lower()
                if not any(lbl.lower() in lower for lbl in labels):
                    continue
            out.append(
                ExtractionCandidate(
                    field=str(field),
                    value=snippet,
                    source="regex",
                    confidence=0.85,
                    block_id=b.id,
                    page=b.page,
                    evidence_text=snippet,
                    bbox=b.bbox,
                    section_label=b.section_label,
                )
            )
    return out


def extract_regex_from_schema(
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
) -> list[ExtractionCandidate]:
    """Run each field's ``regex_hint`` against all blocks (confidence 0.9)."""

    out: list[ExtractionCandidate] = []
    for field, spec in (fields_spec or {}).items():
        if not isinstance(spec, dict):
            continue
        hint = str(spec.get("regex_hint") or "").strip()
        if hint:
            try:
                rx = re.compile(hint)
            except re.error:
                rx = None
            if rx is not None:
                seen_block_val: set[tuple[str, str]] = set()
                for b in blocks:
                    text = b.text or ""
                    for m in rx.finditer(text):
                        raw = m.group(m.lastindex or 1) if m.lastindex else m.group(0)
                        val = _coerce_value(raw, spec)
                        if val is None:
                            continue
                        vkey = (b.id, str(val).lower())
                        if vkey in seen_block_val:
                            continue
                        seen_block_val.add(vkey)
                        if field == "total_due" or str(spec.get("semantic_role") or "") == "document_total":
                            ctx = text.lower()
                            if not any(
                                p in ctx
                                for p in (
                                    "importe por pagar",
                                    "total due",
                                    "amount due",
                                    "total a pagar",
                                )
                            ):
                                if "subtotal" in ctx or "unit price" in ctx or "precio" in ctx:
                                    continue
                        out.append(
                            ExtractionCandidate(
                                field=str(field),
                                value=val,
                                source="regex",
                                confidence=0.9,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=m.group(0).strip(),
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
                        break
        if spec.get("type") == "date" and (
            not hint or not re.search(r"de\s+\w+\s+de", hint, re.IGNORECASE)
        ):
            out.extend(_spanish_date_candidates(field, spec, blocks))
    return out


def _layout_candidate_score(c: ExtractionCandidate) -> tuple[float, int]:
    """Prefer higher confidence and shorter string values (avoids glued multi-field blobs)."""

    text_len = len(str(c.value))
    return (c.confidence, -text_len)


def extract_layout_from_schema(
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
) -> list[ExtractionCandidate]:
    """Match field labels / aliases in block text (PDFs with glued label+value lines)."""

    best: dict[str, ExtractionCandidate] = {}
    for field, spec in (fields_spec or {}).items():
        if not isinstance(spec, dict):
            continue
        # Wine fields use dedicated regex extractors; layout+aliases caused duplicate/conflicting hits.
        if spec.get("aliases") and field in ("ph", "alcohol", "quality"):
            continue
        labels = _labels_for_field(field, spec)
        typ = spec.get("type")

        if typ == "string" and "email" in field.lower():
            role = str(spec.get("semantic_role") or "").lower()
            hint = str(spec.get("regex_hint") or "").strip()
            hint_rx = re.compile(hint) if hint else None
            recipient_blocks = blocks
            if role == "recipient":
                recipient_blocks = [
                    b
                    for b in blocks
                    if any(
                        k in (b.text or "").lower()
                        for k in ("facturar", "bill to", "bill-to", "recipient", "destinatario")
                    )
                ] or blocks
            for b in recipient_blocks:
                text = b.text or ""
                if hint_rx:
                    m = hint_rx.search(text)
                    if m:
                        email = m.group(0)
                        best[field] = ExtractionCandidate(
                            field=field,
                            value=email,
                            source="layout",
                            confidence=0.92,
                            block_id=b.id,
                            page=b.page,
                            evidence_text=email,
                            bbox=b.bbox,
                            section_label=b.section_label,
                        )
                        break
                    continue
                m = _EMAIL_RE.search(text)
                if m:
                    cand = ExtractionCandidate(
                        field=field,
                        value=m.group(0),
                        source="layout",
                        confidence=0.75,
                        block_id=b.id,
                        page=b.page,
                        evidence_text=m.group(0),
                        bbox=b.bbox,
                        section_label=b.section_label,
                    )
                    prev = best.get(field)
                    if prev is None or _layout_candidate_score(cand) > _layout_candidate_score(prev):
                        best[field] = cand
            continue

        for label in labels:
            if not label:
                continue
            escaped = re.escape(label)
            patterns = [
                re.compile(rf"(?i){escaped}\s*[:=]\s*(.+?)\s*$"),
                re.compile(rf"(?i){escaped}\s*(.+?)\s*$"),
            ]
            field_done = False
            for b in blocks:
                text = (b.text or "").strip()
                if not text:
                    continue
                for line in text.splitlines() or [text]:
                    lt = line.strip()
                    if not lt:
                        continue
                    for pat in patterns:
                        m = pat.search(lt)
                        if not m:
                            continue
                        raw = m.group(1).strip()
                        if "invoice_number" in field and "total due" in raw.lower():
                            continue
                        val = _coerce_value(raw, spec)
                        if val is None:
                            continue
                        cand = ExtractionCandidate(
                            field=field,
                            value=val,
                            source="layout",
                            confidence=0.6,
                            block_id=b.id,
                            page=b.page,
                            evidence_text=lt[:280],
                            bbox=b.bbox,
                            section_label=b.section_label,
                        )
                        prev = best.get(field)
                        if prev is None or _layout_candidate_score(cand) > _layout_candidate_score(prev):
                            best[field] = cand
                        field_done = True
                        break
                    if field_done:
                        break
                if field_done:
                    break
            if field_done:
                break
    return list(best.values())


def ensemble_schema_extractors(
    blocks: list[TextBlock],
    fields_spec: dict[str, Any],
) -> list[ExtractionCandidate]:
    """Regex hints plus label/alias layout extraction for arbitrary schema keys."""

    return extract_regex_from_schema(blocks, fields_spec) + extract_layout_from_schema(
        blocks, fields_spec
    )
