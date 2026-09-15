"""Wine QA-style ensemble extractors: regex and layout heuristics over ``TextBlock``s."""

from __future__ import annotations

import re

from ocean_read.domain.validation.pdf_blocks import TextBlock
from ocean_read.domain.validation.resolution import ExtractionCandidate

_PH_RE = re.compile(r"(?i)p[hH]\s*[:=]\s*([\d.]+)")
_PH_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PH_RE,
    re.compile(r"(?i)measured\s+p[hH]\s*[:=]\s*([\d.]+)"),
    re.compile(r"(?i)p[hH]\s+level\s*[:=]?\s*([\d.]+)"),
    re.compile(r"(?i)p[hH]\s+value\s*[:=]?\s*([\d.]+)"),
)
_ALCOHOL_RE = re.compile(r"(?i)alcohol\s*[:=]\s*([\d.]+)\s*%?")
_ALCOHOL_LOOSE_RE = re.compile(r"(?i)alcohol(?!\s*[:=]\s*[\d.])(?:\s+\w+){0,8}\s+(?:at\s+)?([\d.]+)")
_QUALITY_RE = re.compile(r"(?i)quality\s*[:=]\s*([\d.]+)")
_FLOAT_RE = re.compile(r"[\d.]+")


def _safe_float(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None


def _append_candidate(
    out: list[ExtractionCandidate],
    *,
    field: str,
    value: float,
    source: str,
    confidence: float,
    block: TextBlock,
    evidence_text: str,
) -> None:
    out.append(
        ExtractionCandidate(
            field=field,
            value=value,
            source=source,
            confidence=confidence,
            block_id=block.id,
            page=block.page,
            evidence_text=evidence_text[:280],
            bbox=block.bbox,
            section_label=block.section_label,
        )
    )


def extract_regex_wine(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """High-confidence patterns anchored to each block (evidence = matched span)."""

    out: list[ExtractionCandidate] = []
    for b in blocks:
        t = b.text
        for rx in _PH_PATTERNS:
            for m in rx.finditer(t):
                val = _safe_float(m.group(1))
                if val is None:
                    continue
                _append_candidate(
                    out,
                    field="ph",
                    value=val,
                    source="regex",
                    confidence=0.95,
                    block=b,
                    evidence_text=m.group(0).strip() or t[:280],
                )
        for field, rx, conf in (
            ("alcohol", _ALCOHOL_RE, 0.95),
            ("quality", _QUALITY_RE, 0.95),
        ):
            for m in rx.finditer(t):
                val = _safe_float(m.group(1))
                if val is None:
                    continue
                _append_candidate(
                    out,
                    field=field,
                    value=val,
                    source="regex",
                    confidence=conf,
                    block=b,
                    evidence_text=m.group(0).strip() or t[:280],
                )
    return out


def extract_layout_wine(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """Lower-confidence line heuristics when labels appear without strict regex match."""

    out: list[ExtractionCandidate] = []
    for b in blocks:
        for line in b.text.splitlines() or [b.text]:
            lt = line.strip()
            if not lt:
                continue
            lower = lt.lower()
            # Alcohol: prefer anchored pattern so glued Docling blobs do not pick unrelated floats.
            if "alcohol" in lower:
                seen_alcohol: set[float] = set()
                for m in _ALCOHOL_RE.finditer(lt):
                    v = _safe_float(m.group(1))
                    if v is None:
                        continue
                    seen_alcohol.add(v)
                    _append_candidate(
                        out,
                        field="alcohol",
                        value=v,
                        source="layout",
                        confidence=0.55,
                        block=b,
                        evidence_text=m.group(0).strip(),
                    )
                for m in _ALCOHOL_LOOSE_RE.finditer(lt):
                    v = _safe_float(m.group(1))
                    if v is None or v in seen_alcohol:
                        continue
                    seen_alcohol.add(v)
                    _append_candidate(
                        out,
                        field="alcohol",
                        value=v,
                        source="layout",
                        confidence=0.55,
                        block=b,
                        evidence_text=m.group(0).strip(),
                    )
                if not seen_alcohol:
                    nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                    if nums:
                        v = _safe_float(nums[-1])
                        if v is not None:
                            _append_candidate(
                                out,
                                field="alcohol",
                                value=v,
                                source="layout",
                                confidence=0.55,
                                block=b,
                                evidence_text=lt,
                            )
            if lower.startswith("ph") or " ph " in f" {lower} ":
                seen_ph: set[float] = set()
                for rx in _PH_PATTERNS:
                    for m in rx.finditer(lt):
                        v = _safe_float(m.group(1))
                        if v is None or not (0 < v < 14) or v in seen_ph:
                            continue
                        seen_ph.add(v)
                        _append_candidate(
                            out,
                            field="ph",
                            value=v,
                            source="layout",
                            confidence=0.5,
                            block=b,
                            evidence_text=m.group(0).strip(),
                        )
                if not seen_ph:
                    nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                    if nums:
                        v = _safe_float(nums[0])
                        if v is not None and 0 < v < 14:
                            _append_candidate(
                                out,
                                field="ph",
                                value=v,
                                source="layout",
                                confidence=0.5,
                                block=b,
                                evidence_text=lt,
                            )
            if "quality" in lower:
                m = _QUALITY_RE.search(lt)
                if m:
                    v = _safe_float(m.group(1))
                    if v is not None:
                        out.append(
                            ExtractionCandidate(
                                field="quality",
                                value=v,
                                source="layout",
                                confidence=0.5,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=m.group(0).strip()[:280],
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
                    continue
                nums = [x for x in _FLOAT_RE.findall(lt) if _safe_float(x) is not None]
                if nums:
                    v = _safe_float(nums[-1])
                    if v is not None:
                        out.append(
                            ExtractionCandidate(
                                field="quality",
                                value=v,
                                source="layout",
                                confidence=0.5,
                                block_id=b.id,
                                page=b.page,
                                evidence_text=lt[:280],
                                bbox=b.bbox,
                                section_label=b.section_label,
                            )
                        )
    return out


def ensemble_wine_extractors(blocks: list[TextBlock]) -> list[ExtractionCandidate]:
    """Regex + layout candidates (LLM is appended by the application layer)."""

    return extract_regex_wine(blocks) + extract_layout_wine(blocks)
