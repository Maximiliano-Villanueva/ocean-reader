/**
 * Build PDF overlay highlights from validation evidence, errors, and pipeline snapshots.
 * Bboxes use PyMuPDF layout coordinates: ``[x0, y0, x1, y1]`` in PDF points, origin top-left.
 */

import type { ValidationEvidenceOut, ValidateDocumentResponse } from "../api";

export type HighlightKind = "field" | "error" | "ambiguous" | "candidate" | "block";

export type PdfHighlight = {
  id: string;
  page: number;
  bbox: [number, number, number, number];
  label: string;
  kind: HighlightKind;
  /** Optional link to ledger / error row */
  field?: string;
  rule?: string;
};

export type PipelineBlock = {
  id: string;
  page: number;
  bbox?: number[] | null;
  text?: string;
};

export type PipelineCandidate = {
  field: string;
  value?: unknown;
  source?: string;
  confidence?: number;
  block_id?: string;
  page?: number;
  bbox?: number[] | null;
  evidence_text?: string;
};

function isValidBbox(b: unknown): b is [number, number, number, number] {
  if (!Array.isArray(b) || b.length < 4) return false;
  const [x0, y0, x1, y1] = b;
  return (
    typeof x0 === "number" &&
    typeof y0 === "number" &&
    typeof x1 === "number" &&
    typeof y1 === "number" &&
    x1 > x0 &&
    y1 > y0
  );
}

function evidenceToHighlight(
  ev: ValidationEvidenceOut,
  opts: { id: string; label: string; kind: HighlightKind; field?: string; rule?: string },
): PdfHighlight | null {
  if (!isValidBbox(ev.bbox)) return null;
  const page = typeof ev.page === "number" && ev.page > 0 ? ev.page : 1;
  return {
    id: opts.id,
    page,
    bbox: ev.bbox,
    label: opts.label,
    kind: opts.kind,
    field: opts.field,
    rule: opts.rule,
  };
}

/** Cross-field rules may attach ``by_field`` maps instead of a single block bbox. */
function highlightsFromEvidenceValue(
  ev: ValidationEvidenceOut | Record<string, unknown> | null | undefined,
  opts: { idPrefix: string; label: string; kind: HighlightKind; field?: string; rule?: string },
): PdfHighlight[] {
  if (!ev || typeof ev !== "object") return [];
  const raw = ev as Record<string, unknown>;
  const byField = raw.by_field;
  if (byField && typeof byField === "object") {
    const out: PdfHighlight[] = [];
    let i = 0;
    for (const [fname, sub] of Object.entries(byField as Record<string, ValidationEvidenceOut>)) {
      if (!sub || typeof sub !== "object") continue;
      const h = evidenceToHighlight(sub, {
        id: `${opts.idPrefix}-${fname}-${i++}`,
        label: `${opts.label} · ${fname}`,
        kind: opts.kind,
        field: fname,
        rule: opts.rule,
      });
      if (h) out.push(h);
    }
    return out;
  }
  const single = evidenceToHighlight(ev as ValidationEvidenceOut, {
    id: opts.idPrefix,
    label: opts.label,
    kind: opts.kind,
    field: opts.field,
    rule: opts.rule,
  });
  return single ? [single] : [];
}

/** Highlights from API validation report (errors + rule ledger evidence). */
export function highlightsFromReport(report: ValidateDocumentResponse): PdfHighlight[] {
  const out: PdfHighlight[] = [];
  let n = 0;

  for (const r of report.results ?? []) {
    if (!r.evidence) continue;
    out.push(
      ...highlightsFromEvidenceValue(r.evidence, {
        idPrefix: `err-${r.field}-${r.rule}-${n++}`,
        label: `${r.field} (${r.rule})`,
        kind: "error",
        field: r.field,
        rule: r.rule,
      }),
    );
  }

  for (const o of report.field_rule_outcomes ?? []) {
    if (!o.evidence) continue;
    const kind: HighlightKind = o.passed ? "field" : "error";
    out.push(
      ...highlightsFromEvidenceValue(o.evidence, {
        idPrefix: `out-${o.field}-${o.rule}-${n++}`,
        label: `${o.field} · ${o.rule}`,
        kind,
        field: o.field,
        rule: o.rule,
      }),
    );
  }

  return dedupeHighlights(out);
}

export type HighlightsFromCandidatesOptions = {
  /**
   * Schema fields with conflicting extractions (``report.ambiguous_fields``).
   * Only these use the dashed candidate style; other fields use resolved ``field`` (green).
   */
  ambiguousFields?: Iterable<string>;
};

/** All extraction candidates from a persisted run snapshot. */
export function highlightsFromCandidates(
  candidates: PipelineCandidate[],
  opts?: HighlightsFromCandidatesOptions,
): PdfHighlight[] {
  const ambiguous = new Set(opts?.ambiguousFields ?? []);
  const out: PdfHighlight[] = [];
  let n = 0;
  for (const c of candidates) {
    if (!isValidBbox(c.bbox)) continue;
    const page = typeof c.page === "number" && c.page > 0 ? c.page : 1;
    const src = c.source ? ` · ${c.source}` : "";
    const field = c.field;
    const kind: HighlightKind =
      ambiguous.size > 0 && field && ambiguous.has(field) ? "candidate" : "field";
    out.push({
      id: `cand-${field}-${c.block_id ?? n}-${n++}`,
      page,
      bbox: c.bbox,
      label: `${field}${src}`,
      kind,
      field,
    });
  }
  return dedupeHighlights(out);
}

/** Snapshot overlays when the report has no rule ledger (typical AMBIGUOUS early exit). */
export function highlightsFromPipelineSnapshot(
  report: ValidateDocumentResponse,
  candidates: PipelineCandidate[],
  blocks: PipelineBlock[],
): PdfHighlight[] {
  const ambiguousFields = (report.ambiguous_fields ?? []).map((a) => a.field);
  if (candidates.length > 0) {
    return highlightsFromCandidates(candidates, { ambiguousFields });
  }
  return highlightsFromBlocks(blocks);
}

/** Layout blocks (fainter overlays) when candidates lack bbox. */
export function highlightsFromBlocks(blocks: PipelineBlock[]): PdfHighlight[] {
  const out: PdfHighlight[] = [];
  for (const b of blocks) {
    if (!isValidBbox(b.bbox)) continue;
    const page = typeof b.page === "number" && b.page > 0 ? b.page : 1;
    const preview = (b.text ?? "").trim().slice(0, 40);
    out.push({
      id: `blk-${b.id}`,
      page,
      bbox: b.bbox,
      label: preview || b.id,
      kind: "block",
    });
  }
  return dedupeHighlights(out);
}

/** Merge report evidence with optional snapshot candidates/blocks. */
export function mergeHighlights(
  primary: PdfHighlight[],
  extras: PdfHighlight[],
  opts?: { includeBlocks?: boolean },
): PdfHighlight[] {
  const merged = dedupeHighlights([...primary, ...extras]);
  if (!opts?.includeBlocks) {
    return merged.filter((h) => h.kind !== "block");
  }
  return merged;
}

const HIGHLIGHT_KIND_PRIORITY: Record<HighlightKind, number> = {
  error: 4,
  field: 3,
  ambiguous: 2,
  candidate: 2,
  block: 1,
};

function dedupeHighlights(items: PdfHighlight[]): PdfHighlight[] {
  const byRegion = new Map<string, PdfHighlight>();
  for (const h of items) {
    const regionKey = `${h.page}:${h.bbox.map((x) => x.toFixed(1)).join(",")}:${h.field ?? ""}`;
    const existing = byRegion.get(regionKey);
    if (
      !existing ||
      HIGHLIGHT_KIND_PRIORITY[h.kind] > HIGHLIGHT_KIND_PRIORITY[existing.kind]
    ) {
      byRegion.set(regionKey, h);
    }
  }
  return [...byRegion.values()];
}

export function pageNumbersFromHighlights(highlights: PdfHighlight[]): number[] {
  const pages = new Set(highlights.map((h) => h.page));
  if (pages.size === 0) return [1];
  return [...pages].sort((a, b) => a - b);
}
